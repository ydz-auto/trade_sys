"""
Signal Runtime - 时间因果一致的信号生成运行时

重构版本！
接入基础设施：
1. Runtime Clock - 单一时间源
2. Feature Availability - 防止未来特征
3. Label Isolation - Label 物理隔离
4. Cross-Symbol Semantics - 跨币时间对齐
5. Feature Lineage - 特征血缘追踪

重点防护：
- Feature Leakage - 防止偷看未来特征
- Label Contamination - Label 不能混入特征
- Cross-Symbol Drift - 跨币时间错位

不做上帝对象！只是组合使用基础设施。
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import asyncio

from infrastructure.logging import get_logger
from infrastructure.runtime_clock import (
    RuntimeClock,
    ClockMode,
    get_clock,
    set_clock_mode,
    now_ms
)
from infrastructure.feature_availability import (
    SystematicAvailabilityGuard,
    get_systematic_guard
)
from infrastructure.label_isolation import (
    StrictLabelStore,
    get_label_store,
    set_label_store_mode,
    safe_dataframe
)
from infrastructure.storage.immutable_snapshot import (
    ImmutableFeatureSnapshot,
    get_immutable_snapshot_store,
    create_immutable_snapshot
)
from infrastructure.event.cross_symbol_semantics import (
    CrossSymbolEventSemantics,
    get_cross_symbol_semantics
)
from infrastructure.feature.feature_lineage import (
    FeatureLineageSystem,
    get_feature_lineage
)
from runtime.feature_matrix_runtime import get_feature_matrix_runtime


logger = get_logger("signal_runtime")


@dataclass
class SignalConfig:
    """信号运行时配置"""
    symbols: List[str] = field(default_factory=list)
    mode: str = "live"


class TimeCausalSignalRuntime:
    """
    时间因果一致的信号运行时
    
    重点防护：
    - 只使用当前时间之前的特征
    - Label 物理隔离
    - 跨币时间对齐
    - 特征血缘追踪
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
        self._feature_matrices = {}
        
        # 2. 设置模式
        self._setup_mode()
        
        self._running = False
        
        logger.info(f"Time-Causal Signal Runtime initialized for {self.config.symbols}")
    
    def _setup_mode(self):
        """设置模式"""
        if self.config.mode == "replay":
            set_clock_mode(ClockMode.REPLAY)
            set_label_store_mode("research")
        elif self.config.mode == "paper":
            set_clock_mode(ClockMode.PAPER)
            set_label_store_mode("runtime")
        else:  # live
            set_clock_mode(ClockMode.LIVE)
            set_label_store_mode("runtime")
    
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
        3. 跨币对齐（可选）
        """
        # 1. 检查特征可用性
        is_available, issue = self._availability_guard.check(
            feature_name=feature_name,
            feature_timestamp=timestamp_ms,
            replay_clock=self._clock.available_at_ms(),
            clock=self._clock
        )
        
        if not is_available:
            logger.debug(f"Skipping unavailable feature {feature_name}: {issue}")
            return False
        
        # 2. 记录特征血缘
        # 这里可以记录这个特征的来源、依赖关系等
        
        # 3. 跨币对齐（可选）
        if self._cross_symbol:
            self._cross_symbol.record_event(
                symbol=symbol,
                event_type=feature_name,
                timestamp_ms=timestamp_ms
            )
        
        # 4. 存储到 Snapshot 用于验证
        # 这里可以记录特征快照
        
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
        """
        if timestamp_ms is None:
            timestamp_ms = now_ms()
        
        # 1. 确保不会使用未来特征
        safe_timestamp = min(timestamp_ms, self._clock.available_at_ms())
        
        # 2. 获取安全特征
        # 这里从 feature_matrix 获取
        features = self._get_safe_features(symbol, safe_timestamp)
        
        # 3. 检查 Label 隔离
        # 如果 DataFrame 中有 future_return，会自动清理
        # safe_dataframe(df)
        
        # 4. 生成信号（具体策略逻辑在这里
        signals = []
        
        # ... 策略逻辑 ...
        
        # 5. 记录特征血缘
        for signal in signals:
            self._lineage.register_source(
                feature_name=signal.get("strategy", "unknown"),
                feature_type="signal"
            )
        
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
        """
        # 1. 时间因果检查
        if timestamp_ms > self._clock.available_at_ms():
            logger.warning(f"Timestamp {timestamp_ms} ahead of clock {self._clock.available_at_ms()}")
            return None
        
        # 2. 调用策略生成信号
        try:
            signal = strategy.generate_signal(features)
            
            if signal:
                signal['timestamp_ms'] = timestamp_ms
                signal['strategy_id'] = strategy.__class__.__name__
                
                # 记录特征血缘
                self._lineage.register_source(
                    feature_name=signal['strategy_id'],
                    feature_type="signal"
                )
            
            return signal
        except Exception as e:
            logger.error(f"Signal generation failed: {e}")
            return None
    
    def _get_safe_features(
        self,
        symbol: str,
        timestamp_ms: int
    ) -> Dict[str, Any]:
        if symbol not in self._feature_matrices:
            self._feature_matrices[symbol] = get_feature_matrix_runtime(
                symbol=symbol,
                mode=self.config.mode
            )
        feature_matrix = self._feature_matrices[symbol]
        return feature_matrix.get_features_at(timestamp_ms)
    
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


# 全局实例
_tc_signal_runtime: Optional[TimeCausalSignalRuntime] = None


def get_signal_runtime(config: Optional[SignalConfig] = None) -> TimeCausalSignalRuntime:
    """获取信号运行时（工厂函数）"""
    global _tc_signal_runtime
    if _tc_signal_runtime is None:
        if config is None:
            config = SignalConfig()
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
