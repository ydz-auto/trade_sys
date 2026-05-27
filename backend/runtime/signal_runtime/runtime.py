"""
Signal Runtime - 时间因果一致的信号生成运行时

重构版本！
接入基础设施：
1. Runtime Clock - 单一时间源
2. Feature Availability - 防止未来特征
3. Label Isolation - Label 物理隔离
4. Cross-Symbol Semantics - 跨币种时间对齐
5. Feature Lineage - 特征血缘追踪

重点防护：
- Feature Leakage - 防止偷看未来特征
- Label Contamination - Label 不能混入特征
- Cross-Symbol Drift - 跨币种时间错位

不做上帝对象！只是组合使用基础设施。
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import asyncio

from infrastructure.logging import get_logger
from infrastructure.utilities.runtime_clock import (
    RuntimeClock,
    ClockMode,
    get_clock,
    set_clock_mode,
    now_ms
)
from domain.feature.availability import (
    SystematicAvailabilityGuard,
    get_systematic_guard
)
from domain.feature.label_isolation import (
    StrictLabelStore,
    get_label_store,
    safe_dataframe
)
from infrastructure.storage.immutable_snapshot import (
    ImmutableFeatureSnapshot,
    get_immutable_snapshot_store,
    create_immutable_snapshot
)
from domain.event.infrastructure.cross_symbol_semantics import (
    CrossSymbolEventSemantics,
    get_cross_symbol_semantics
)
from domain.feature.infrastructure.feature_lineage import (
    FeatureLineageSystem,
    get_feature_lineage
)
from runtime.feature_runtime import get_feature_runtime, FeatureConfig, FeatureMode
from engines.compute.strategy.registry import (
    get_strategy,
    list_strategies,
    get_strategy_info,
)
from runtime.regime_runtime import get_regime_runtime


logger = get_logger("signal_runtime")


class SignalType(Enum):
    """信号类型"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class SignalConfig:
    """信号运行时配置"""
    symbols: List[str] = field(default_factory=list)
    mode: str = "live"
    enable_strategy_registry: bool = True


class TimeCausalSignalRuntime:
    """
    时间因果一致的信号运行时
    
    重点防护：
    - 只使用当前时间之前的特征
    - Label 物理隔离
    - 跨币种时间对齐
    - 特征血缘追踪
    
    新增功能：
    - 自动从 Registry 加载策略
    - Regime Runtime 集成（策略权重/启用）
    """
    
    def __init__(
        self,
        config: Optional[SignalConfig] = None
    ):
        self.config = config or SignalConfig()
        
        # 1. 初始化基础设施（不是上帝对象！只是组合使用！）
        self._clock = get_clock()
        self._availability_guard = get_systematic_guard()
        self._label_store = get_label_store()
        self._snapshot_store = get_immutable_snapshot_store("MULTI")
        self._cross_symbol = get_cross_symbol_semantics(self.config.symbols)
        self._lineage = get_feature_lineage()
        self._feature_runtimes = {}
        
        # 2. 策略注册表和信号历史
        self._strategies: Dict[str, Any] = {}
        self._signal_history: List[Dict[str, Any]] = []
        self._signal_callbacks: List[Callable] = []
        self._signal_sequence = 0
        
        # 3. Regime Runtime 集成
        self._regime_runtime = None
        
        # 4. 设置模式
        self._setup_mode()
        
        self._running = False
        
        logger.info(f"Time-Causal Signal Runtime initialized for {self.config.symbols}")
    
    def load_strategies_from_registry(self, strategy_ids: Optional[List[str]] = None,
                                     tier: Optional[int] = None,
                                     symbol: Optional[str] = None) -> int:
        """
        从策略注册表加载策略
        
        参数：
            strategy_ids: 要加载的策略ID列表，None则加载所有
            tier: 只加载指定梯队的策略
            symbol: 为特定币种加载策略
        """
        if strategy_ids is None:
            # 获取所有策略信息
            strategy_info_list = list_strategies()
            strategy_ids = [s.strategy_id for s in strategy_info_list]
        
        loaded_count = 0
        
        for strategy_id in strategy_ids:
            try:
                # 获取策略信息
                info = get_strategy_info(strategy_id)
                if info:
                    # 梯队过滤
                    if tier is not None and info.tier != tier:
                        continue
                    
                    # 币种支持过滤
                    if symbol and info.supported_symbols and symbol not in info.supported_symbols:
                        continue
                
                # 加载策略
                strategy = get_strategy(strategy_id)
                self.register_strategy(strategy_id, strategy)
                
                loaded_count += 1
                logger.info(f"Loaded strategy from registry: {strategy_id}")
                
            except Exception as e:
                logger.error(f"Failed to load strategy {strategy_id}: {e}")
        
        logger.info(f"Loaded {loaded_count} strategies from registry")
        return loaded_count
    
    def attach_regime_runtime(self):
        """连接 Regime Runtime 来动态控制策略"""
        self._regime_runtime = get_regime_runtime()
        logger.info("Attached Regime Runtime to Signal Runtime")
    
    def apply_regime_filter(self):
        """根据 Regime 状态启用/禁用策略"""
        if not self._regime_runtime:
            return
        
        active_strategy_ids = self._regime_runtime.get_active_strategies()
        
        for strategy_id, strategy in self._strategies.items():
            # 检查策略是否应该启用
            base_id = strategy_id.rsplit("_", 1)[0] if "_" in strategy_id else strategy_id
            
            should_enable = (
                base_id in active_strategy_ids or
                strategy_id in active_strategy_ids or
                not active_strategy_ids  # 如果没有指定策略，都启用
            )
            
            if should_enable and not strategy.is_enabled:
                strategy.enable()
                logger.debug(f"Regime enabled: {strategy_id}")
            elif not should_enable and strategy.is_enabled:
                strategy.disable()
                logger.debug(f"Regime disabled: {strategy_id}")
    
    def _setup_mode(self):
        """设置模式"""
        self._mode = self.config.mode
        if self.config.mode == "replay":
            set_clock_mode(ClockMode.REPLAY)
            from domain.feature.label_isolation import set_label_store_mode
            set_label_store_mode("research")
        elif self.config.mode == "paper":
            set_clock_mode(ClockMode.PAPER)
            from domain.feature.label_isolation import set_label_store_mode
            set_label_store_mode("runtime")
        else:  # live
            set_clock_mode(ClockMode.LIVE)
            from domain.feature.label_isolation import set_label_store_mode
            set_label_store_mode("runtime")
    
    def register_strategy(self, strategy_id: str, strategy: Any) -> None:
        """
        注册策略
        
        Args:
            strategy_id: 策略唯一标识符
            strategy: 策略实例，必须实现 generate_signal 方法
        """
        self._strategies[strategy_id] = strategy
        logger.info(f"Strategy registered: {strategy_id}")
    
    def unregister_strategy(self, strategy_id: str) -> None:
        """注销策略"""
        if strategy_id in self._strategies:
            del self._strategies[strategy_id]
            logger.info(f"Strategy unregistered: {strategy_id}")
    
    def get_registered_strategies(self) -> List[str]:
        """获取已注册策略列表"""
        return list(self._strategies.keys())
    
    def add_signal_callback(self, callback: Callable) -> None:
        """
        添加信号回调函数
        """
        self._signal_callbacks.append(callback)
    
    async def initialize(self, symbol: Optional[str] = None, mode: Optional[str] = None,
                        auto_load_strategies: bool = True) -> None:
        """
        初始化信号运行时（供 ReplayRuntime 调用）
        
        新增功能：
            auto_load_strategies: 是否自动从 registry 加载策略
        """
        if symbol and symbol not in self.config.symbols:
            self.config.symbols.append(symbol)
        if mode:
            self.config.mode = mode
            self._mode = mode  # 同步设置 _mode，否则 generate_signal() 中的时间检查会失败
            self._setup_mode()
        
        # 自动从 registry 加载策略
        if auto_load_strategies and self.config.enable_strategy_registry:
            try:
                # 先加载第一梯队策略（高优先级）
                tier1_count = self.load_strategies_from_registry(tier=1, symbol=symbol)
                # 再加载第二梯队策略
                tier2_count = self.load_strategies_from_registry(tier=2, symbol=symbol)
                logger.info(f"Auto-loaded {tier1_count} tier 1 strategies and {tier2_count} tier 2 strategies")
            except Exception as e:
                logger.warning(f"Failed to auto-load strategies: {e}")
        
        # 尝试连接 Regime Runtime
        try:
            self.attach_regime_runtime()
        except Exception as e:
            logger.warning(f"Failed to attach Regime Runtime: {e}")
        
        logger.info(f"Signal Runtime initialized for {self.config.symbols}")
    
    async def update_feature(
        self,
        symbol: str,
        feature_name: str,
        feature_value: Any,
        timestamp_ms: int
    ) -> bool:
        """
        更新特征（时间因果安全）
        
        重点防护：
        1. 特征可用性检查
        2. 特征血缘追踪
        3. 跨币种对齐（可选）
        """
        # 1. 检查特征可用性
        from domain.feature.availability import AvailabilityStatus
        status = self._availability_guard.check(
            feature_name=feature_name,
            feature_timestamp=timestamp_ms,
            query_time=self._clock.available_at_ms(),
            clock=self._clock
        )
        
        if status != AvailabilityStatus.AVAILABLE:
            logger.debug(f"Skipping unavailable feature {feature_name}: {status.value}")
            return False
        
        # 2. 记录特征血缘
        self._lineage.register_source(feature_name, "feature")
        
        # 3. 跨币种对齐（可选）
        if self._cross_symbol:
            self._cross_symbol.record_event(
                symbol=symbol,
                event_type=feature_name,
                timestamp_ms=timestamp_ms
            )
        
        return True
    
    async def generate_signals(
        self,
        symbol: str,
        timestamp_ms: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        生成信号（时间因果安全）
        
        重点防护：
        1. 只能使用 <= 当前时间的特征
        2. Label 隔离（不能在特征中混入 future_return）
        
        新增功能：
        - Regime 过滤
        """
        if timestamp_ms is None:
            timestamp_ms = now_ms()
        
        # 0. 应用 Regime 过滤器（动态启用/禁用策略）
        self.apply_regime_filter()
        
        # 1. 确保不会使用未来特征
        safe_timestamp = min(timestamp_ms, self._clock.available_at_ms())
        
        # 2. 获取安全特征
        features = await self._get_safe_features(symbol, safe_timestamp)
        
        # 3. 调用所有已注册且启用的策略生成信号
        signals = []
        for strategy_id, strategy in self._strategies.items():
            try:
                # 跳过禁用的策略
                if not strategy.is_enabled:
                    continue
                
                signal = await self.generate_signal(strategy, features, safe_timestamp)
                if signal:
                    signal['strategy_id'] = strategy_id
                    signal['symbol'] = symbol
                    signals.append(signal)
                    
                    # 记录到历史
                    self._signal_history.append(signal)
                    self._signal_sequence += 1
                    
                    # 调用回调
                    for callback in self._signal_callbacks:
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(signal)
                            else:
                                callback(signal)
                        except Exception as e:
                            logger.error(f"Signal callback failed: {e}")
            
            except Exception as e:
                logger.error(f"Strategy {strategy_id} signal generation failed: {e}")
        
        return signals
    
    async def generate_signal(
        self,
        strategy,
        features: Dict[str, Any],
        timestamp_ms: int
    ) -> Optional[Dict[str, Any]]:
        """
        为指定策略生成信号（供 ReplayRuntime 调用）
        
        Args:
            strategy: 策略对象
            features: 特征字典
            timestamp_ms: 时间戳（毫秒）
        
        Returns:
            Signal 字典或 None
        
        Raises:
            Exception: 当信号生成过程中发生错误时抛出异常（便于 ReplayRuntime 捕获）
        """
        # 1. 时间因果检查 — replay 模式下先推进时钟
        if self._mode == "replay":
            self._clock.advance_to(timestamp_ms)
        else:
            if timestamp_ms > self._clock.available_at_ms() + 5000:
                logger.warning(f"Timestamp {timestamp_ms} too far ahead of clock {self._clock.available_at_ms()}")
                return None
        
        # 2. 调用策略生成信号
        try:
            signal = strategy.generate_signal(features)
            
            if signal:
                signal['timestamp_ms'] = timestamp_ms
                signal['strategy_id'] = strategy.__class__.__name__
                
                # 记录特征血缘
                from domain.feature.infrastructure.feature_lineage import FeatureType as LineageFeatureType
                self._lineage.register_feature(
                    feature_name=signal['strategy_id'],
                    feature_type=LineageFeatureType.DERIVED,
                )
            
            return signal
        except Exception as e:
            logger.error(f"Signal generation failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # 重新抛出异常，让 ReplayRuntime 可以捕获并记录
            raise
    
    async def _get_safe_features(
        self,
        symbol: str,
        timestamp_ms: int
    ) -> Dict[str, Any]:
        if symbol not in self._feature_runtimes:
            feature_config = FeatureConfig(symbol=symbol, mode=FeatureMode(self.config.mode))
            self._feature_runtimes[symbol] = get_feature_runtime(feature_config)
        
        feature_runtime = self._feature_runtimes[symbol]
        return await feature_runtime.get_features(timestamp_ms)
    
    def get_signal_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取信号历史"""
        return self._signal_history[-limit:]
    
    async def start(self):
        """启动运行时"""
        if self._running:
            return
        self._running = True
        logger.info("Signal runtime started")
    
    async def stop(self):
        """停止运行时"""
        if not self._running:
            return
        self._running = False
        logger.info("Signal runtime stopped")
    
    def is_running(self) -> bool:
        return self._running

    async def on_event(self, event: Any) -> None:
        event_type = getattr(event, "event_type", None) or (event.get("event_type") if isinstance(event, dict) else None)

        if event_type == "feature":
            symbol = getattr(event, "symbol", None) or (event.get("symbol") if isinstance(event, dict) else None)
            feature_name = getattr(event, "feature_name", None) or (event.get("feature_name") if isinstance(event, dict) else None)
            feature_value = getattr(event, "feature_value", None) or (event.get("feature_value") if isinstance(event, dict) else None)
            timestamp_ms = getattr(event, "timestamp_ms", None) or (event.get("timestamp_ms") if isinstance(event, dict) else None)
            if symbol and feature_name and timestamp_ms is not None:
                await self.update_feature(symbol, feature_name, feature_value, timestamp_ms)
        elif event_type == "signal":
            symbol = getattr(event, "symbol", None) or (event.get("symbol") if isinstance(event, dict) else None)
            timestamp_ms = getattr(event, "timestamp_ms", None) or (event.get("timestamp_ms") if isinstance(event, dict) else None)
            if symbol:
                await self.generate_signals(symbol, timestamp_ms)
        else:
            logger.debug(f"Unhandled event_type: {event_type}")

    async def snapshot(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "mode": self.config.mode,
            "symbols": list(self.config.symbols),
            "signal_sequence": self._signal_sequence,
            "strategies": self.get_registered_strategies(),
            "signal_history_count": len(self._signal_history),
            "clock_available_at_ms": self._clock.available_at_ms(),
        }

    async def recover(self, checkpoint: Any = None) -> None:
        if checkpoint is None:
            logger.info("Signal runtime recover: no checkpoint provided, resetting state")
            self._signal_sequence = 0
            self._signal_history = []
            return

        state = checkpoint if isinstance(checkpoint, dict) else {}
        self._signal_sequence = state.get("signal_sequence", 0)
        self._signal_history = state.get("signal_history", [])

    def get_state(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "mode": self.config.mode,
            "symbols": list(self.config.symbols),
            "signal_sequence": self._signal_sequence,
            "strategies": self.get_registered_strategies(),
            "signal_history_count": len(self._signal_history),
        }


# 全局实例
_tc_signal_runtime: Optional[TimeCausalSignalRuntime] = None


def get_signal_runtime(config: Optional[SignalConfig] = None) -> TimeCausalSignalRuntime:
    """获取信号运行时（工厂函数）"""
    global _tc_signal_runtime
    if _tc_signal_runtime is None:
        _tc_signal_runtime = TimeCausalSignalRuntime(config)
    return _tc_signal_runtime


async def main():
    print("=" * 60)
    print("Signal Runtime - Time-Causal Signal Generation")
    print("=" * 60)

    runtime = get_signal_runtime()
    await runtime.start()

    try:
        while runtime.is_running():
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        await runtime.stop()
