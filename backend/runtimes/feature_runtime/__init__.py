"""
Feature Runtime - 真正的特征运行时（单一实现入口）

核心原则：
1. 所有特征计算必须通过这个 Runtime
2. 在线/离线使用完全相同的逻辑
3. 绝对防止 Future Leakage

架构定位：
    Event (Kline/Trade/Orderbook)
         ↓
    FeatureRuntime (唯一入口)
         ↓
    UnifiedFeatureCalculator
         ↓
    PointInTime Store
         ↓
    Feature Matrix

重点防护：
- 禁止直接调用 UnifiedFeatureCalculator.compute()
- 禁止直接读取 parquet 然后 pandas 计算
- 所有特征必须走事件驱动
- 时间因果一致性检查
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
from infrastructure.storage.point_in_time_store import (
    PointInTimeFeatureStore,
    get_point_in_time_store,
    FeatureSourceType
)
from infrastructure.storage.immutable_snapshot import (
    ImmutableFeatureSnapshot,
    get_immutable_snapshot_store,
    create_immutable_snapshot
)
from engines.compute.feature.unified_calculator import UnifiedFeatureCalculator


logger = get_logger("feature_runtime")


class FeatureMode(Enum):
    LIVE = "live"
    REPLAY = "replay"
    PAPER = "paper"


@dataclass
class FeatureConfig:
    """特征运行时配置"""
    symbol: str = "BTCUSDT"
    mode: FeatureMode = FeatureMode.LIVE
    max_lookback: int = 500
    use_gpu: bool = True
    enable_streaming: bool = True


@dataclass
class FeatureEvent:
    """特征事件"""
    event_id: str
    event_type: str  # "kline", "trade", "orderbook"
    timestamp_ms: int
    data: Dict[str, Any]


@dataclass
class FeatureSnapshot:
    """特征快照"""
    snapshot_id: str
    timestamp_ms: int
    features: Dict[str, float]
    symbol: str


class FeatureRuntime:
    """
    真正的特征运行时（按 symbol/mode 隔离）
    
    所有特征计算必须通过这个 Runtime，禁止绕过！
    
    核心能力：
    - 事件驱动的特征计算
    - 在线/离线统一实现
    - 时间因果一致性保障
    - Point-in-Time 存储
    - 不可变快照
    
    重点防护：
    - 禁止直接调用 calculator.compute()
    - 禁止 pandas rolling 直接计算
    - 所有特征必须走事件流
    """
    
    def __init__(self, config: Optional[FeatureConfig] = None):
        self.config = config or FeatureConfig()
        
        # 1. 基础设施
        self._clock = get_clock()
        self._availability_guard = get_systematic_guard()
        self._pit_store = get_point_in_time_store(self.config.symbol)
        self._snapshot_store = get_immutable_snapshot_store(self.config.symbol)
        
        # 2. 统一计算器（隐藏内部，禁止外部直接调用）
        try:
            from infrastructure.acceleration import get_accelerator_info
            _accel_info = get_accelerator_info()
        except Exception:
            _accel_info = None

        self._calculator = UnifiedFeatureCalculator(
            max_lookback=self.config.max_lookback,
            use_gpu=self.config.use_gpu,
            accelerator_info=_accel_info
        )
        
        # 3. 状态
        self._running = False
        self._event_buffer = asyncio.Queue(maxsize=10000)
        self._processing_task = None
        
        # 4. 回调
        self._on_feature_callback = None
        self._on_snapshot_callback = None
        
        # 5. 设置模式
        self._setup_mode()
        
        logger.info(f"FeatureRuntime initialized: {self.config.symbol}, mode={self.config.mode.value}")
    
    def _setup_mode(self):
        """设置运行模式"""
        if self.config.mode == FeatureMode.REPLAY:
            set_clock_mode(ClockMode.REPLAY)
        elif self.config.mode == FeatureMode.PAPER:
            set_clock_mode(ClockMode.PAPER)
        else:
            set_clock_mode(ClockMode.LIVE)
    
    def set_callbacks(
        self,
        on_feature: Optional[Callable] = None,
        on_snapshot: Optional[Callable] = None
    ):
        """设置回调"""
        self._on_feature_callback = on_feature
        self._on_snapshot_callback = on_snapshot
    
    async def initialize(self, symbol: Optional[str] = None, mode: Optional[str] = None):
        """初始化特征运行时（供 ReplayRuntime 调用）"""
        if symbol:
            self.config.symbol = symbol
            # 重新初始化 PIT Store 等基础设施
            self._pit_store = get_point_in_time_store(self.config.symbol)
            self._snapshot_store = get_immutable_snapshot_store(self.config.symbol)
        
        if mode:
            self.config.mode = FeatureMode(mode)
            self._setup_mode()
        
        logger.info(f"FeatureRuntime initialized: {self.config.symbol}, mode={self.config.mode.value}")
    
    async def update(self, event: Any):
        """更新特征（供 ReplayRuntime 调用）"""
        event_type, data, timestamp_ms = self._parse_event(event)
        if event_type:
            if self.config.mode == FeatureMode.REPLAY:
                await self.process_event_immediately(event_type, data, timestamp_ms)
            else:
                await self.emit_event(event_type, data, timestamp_ms)

    async def process_event_immediately(self, event_type: str, data: Dict[str, Any], timestamp_ms: Optional[int] = None):
        """
        同步处理事件 — Replay 模式专用

        与 emit_event() 不同，此方法不经过异步队列，
        而是立即执行特征计算并写入 PIT Store，
        保证调用后 get_features() 能拿到最新结果。
        """
        if timestamp_ms is None:
            timestamp_ms = now_ms()

        event = FeatureEvent(
            event_id=f"{event_type}_{timestamp_ms}",
            event_type=event_type,
            timestamp_ms=timestamp_ms,
            data=data
        )

        await self._process_event(event)

    def _parse_event(self, event: Any):
        """从各种事件格式中提取 event_type / data / timestamp_ms"""
        event_type = getattr(event, 'event_type', None) or (event.get('event_type') if isinstance(event, dict) else None)
        data = getattr(event, 'data', None) or (event.get('data', {}) if isinstance(event, dict) else {})
        timestamp_ms = getattr(event, 'timestamp_ms', None) or (event.get('timestamp_ms') if isinstance(event, dict) else None)

        if not event_type:
            if hasattr(event, 'open') and hasattr(event, 'close'):
                event_type = 'kline'
                data = {
                    'open': getattr(event, 'open', 0),
                    'high': getattr(event, 'high', 0),
                    'low': getattr(event, 'low', 0),
                    'close': getattr(event, 'close', 0),
                    'volume': getattr(event, 'volume', 0),
                    'symbol': getattr(event, 'symbol', self.config.symbol)
                }
                timestamp_ms = getattr(event, 'timestamp_ms', now_ms())

        return event_type, data, timestamp_ms
    
    async def get_features(self, timestamp_ms: int, feature_names: Optional[List[str]] = None) -> Dict[str, float]:
        """获取特征（供 ReplayRuntime 调用）"""
        return self.get_features_at(timestamp_ms, feature_names)
    
    async def start(self):
        """启动特征运行时"""
        if self._running:
            return
        
        self._running = True
        self._processing_task = asyncio.create_task(self._process_event_stream())
        logger.info("FeatureRuntime started")
    
    async def stop(self):
        """停止特征运行时"""
        self._running = False
        
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
        
        logger.info("FeatureRuntime stopped")
    
    async def _process_event_stream(self):
        """处理事件流（核心循环）"""
        while self._running:
            try:
                event = await self._event_buffer.get()
                await self._process_event(event)
                self._event_buffer.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing event: {e}")
    
    async def _process_event(self, event: FeatureEvent):
        """处理单个事件（时间因果安全）"""
        # 1. 在 replay 模式下，先推进时钟再处理事件
        #    live 模式下，事件时间不应超过时钟（但允许微小偏差）
        if self.config.mode == FeatureMode.REPLAY:
            self._clock.advance_to(event.timestamp_ms)
        else:
            if event.timestamp_ms > self._clock.available_at_ms() + 5000:
                logger.warning(f"Event time {event.timestamp_ms} too far ahead of clock!")
                return
        
        # 2. 根据事件类型处理
        event_type_lower = event.event_type.lower() if isinstance(event.event_type, str) else ""
        if event_type_lower == "kline":
            await self._process_kline_event(event)
        elif event_type_lower == "trade":
            await self._process_trade_event(event)
        elif event_type_lower == "orderbook":
            await self._process_orderbook_event(event)
        elif event_type_lower == "funding":
            await self._process_funding_event(event)
        elif event_type_lower == "liquidation":
            await self._process_liquidation_event(event)
        elif event_type_lower == "open_interest":
            await self._process_open_interest_event(event)
        elif event_type_lower == "mark_price":
            await self._process_mark_price_event(event)
        
        # 3. 推进时钟
        self._clock.advance_to(event.timestamp_ms)
    
    async def _process_kline_event(self, event: FeatureEvent):
        """处理 K 线事件"""
        data = event.data
        symbol = data.get('symbol', self.config.symbol)
        
        # 1. 更新计算器（通过 Runtime，禁止直接调用）
        features = self._calculator.compute(
            symbol=symbol,
            open_price=float(data.get('open', 0)),
            high=float(data.get('high', 0)),
            low=float(data.get('low', 0)),
            close=float(data.get('close', 0)),
            volume=float(data.get('volume', 0))
        )
        
        # 2. 存储到 PIT Store
        self._pit_store.store_features_batch(
            features=features,
            feature_timestamp=event.timestamp_ms,
            source_types={feat: FeatureSourceType.DERIVED for feat in features}
        )
        
        # 3. 触发回调
        if self._on_feature_callback:
            await self._on_feature_callback(event.timestamp_ms, features)
    
    async def _process_trade_event(self, event: FeatureEvent):
        """处理交易事件"""
        data = event.data
        symbol = data.get('symbol', self.config.symbol)
        
        # 提取交易列表（支持单个或多个交易）
        trades = data.get('trades', [data])
        
        # 使用 UnifiedFeatureCalculator 计算 Trade 特征
        features = self._calculator.update_trades(
            symbol=symbol,
            trades=trades,
            window_ms=data.get('window_ms', 60000)
        )
        
        # 存储到 PIT Store
        if features:
            self._pit_store.store_features_batch(
                features=features,
                feature_timestamp=event.timestamp_ms,
                source_types={k: FeatureSourceType.DERIVED for k in features}
            )
            
            # 触发回调
            if self._on_feature_callback:
                await self._on_feature_callback(event.timestamp_ms, features)
    
    async def _process_orderbook_event(self, event: FeatureEvent):
        """处理订单簿事件"""
        data = event.data
        symbol = data.get('symbol', self.config.symbol)
        
        book_data = {
            'bid_price_0': float(data.get('bids', [[0, 0]])[0][0]),
            'bid_volume_0': float(data.get('bids', [[0, 0]])[0][1]),
            'ask_price_0': float(data.get('asks', [[0, 0]])[0][0]),
            'ask_volume_0': float(data.get('asks', [[0, 0]])[0][1]),
        }
        
        self._pit_store.store_features_batch(
            features=book_data,
            feature_timestamp=event.timestamp_ms,
            source_types={key: FeatureSourceType.RAW for key in book_data}
        )

    async def _process_funding_event(self, event: FeatureEvent):
        """处理资金费率事件"""
        data = event.data
        funding_rate = float(data.get('funding_rate', 0))
        mark_price = float(data.get('mark_price', 0))
        index_price = float(data.get('index_price', 0))

        features = {
            'funding_rate': funding_rate,
            'funding_mark_price': mark_price,
            'funding_index_price': index_price,
        }

        self._pit_store.store_features_batch(
            features=features,
            feature_timestamp=event.timestamp_ms,
            source_types={k: FeatureSourceType.RAW for k in features}
        )

    async def _process_liquidation_event(self, event: FeatureEvent):
        """处理强平事件"""
        data = event.data
        symbol = data.get('symbol', self.config.symbol)
        
        # 提取爆仓列表（支持单个或多个爆仓）
        liquidations = data.get('liquidations', [data])
        
        # 使用 UnifiedFeatureCalculator 计算 Liquidation 特征
        features = self._calculator.update_liquidations(
            symbol=symbol,
            liquidations=liquidations,
            window_ms=data.get('window_ms', 60000)
        )
        
        # 存储到 PIT Store
        if features:
            self._pit_store.store_features_batch(
                features=features,
                feature_timestamp=event.timestamp_ms,
                source_types={k: FeatureSourceType.DERIVED for k in features}
            )
            
            # 触发回调
            if self._on_feature_callback:
                await self._on_feature_callback(event.timestamp_ms, features)

    async def _process_open_interest_event(self, event: FeatureEvent):
        """处理持仓量事件"""
        data = event.data
        symbol = data.get('symbol', self.config.symbol)
        oi = float(data.get('open_interest', data.get('oi', 0)))
        
        # 使用 UnifiedFeatureCalculator 计算 OI 特征
        features = self._calculator.update_oi(
            symbol=symbol,
            oi=oi,
            timestamp=event.timestamp_ms
        )
        
        # 存储到 PIT Store
        if features:
            self._pit_store.store_features_batch(
                features=features,
                feature_timestamp=event.timestamp_ms,
                source_types={k: FeatureSourceType.DERIVED for k in features}
            )
            
            # 触发回调
            if self._on_feature_callback:
                await self._on_feature_callback(event.timestamp_ms, features)

    async def _process_funding_event(self, event: FeatureEvent):
        """处理资金费率事件"""
        data = event.data
        symbol = data.get('symbol', self.config.symbol)
        funding_rate = float(data.get('funding_rate', 0))
        
        # 使用 UnifiedFeatureCalculator 计算 Funding 特征
        features = self._calculator.update_funding(
            symbol=symbol,
            funding_rate=funding_rate,
            timestamp=event.timestamp_ms
        )
        
        # 存储到 PIT Store
        if features:
            self._pit_store.store_features_batch(
                features=features,
                feature_timestamp=event.timestamp_ms,
                source_types={k: FeatureSourceType.DERIVED for k in features}
            )
            
            # 触发回调
            if self._on_feature_callback:
                await self._on_feature_callback(event.timestamp_ms, features)

    async def _process_mark_price_event(self, event: FeatureEvent):
        """处理标记价格事件"""
        data = event.data
        mark_price = float(data.get('mark_price', 0))
        index_price = float(data.get('index_price', 0))

        features = {
            'mark_price': mark_price,
            'index_price': index_price,
        }

        self._pit_store.store_features_batch(
            features=features,
            feature_timestamp=event.timestamp_ms,
            source_types={k: FeatureSourceType.RAW for k in features}
        )
    
    async def emit_event(self, event_type: str, data: Dict[str, Any], timestamp_ms: Optional[int] = None):
        """
        发射事件到特征运行时
        
        这是唯一的特征输入入口！
        """
        if timestamp_ms is None:
            timestamp_ms = now_ms()
        
        event = FeatureEvent(
            event_id=f"{event_type}_{timestamp_ms}",
            event_type=event_type,
            timestamp_ms=timestamp_ms,
            data=data
        )
        
        await self._event_buffer.put(event)
    
    def get_features_at(self, timestamp_ms: int, feature_names: Optional[List[str]] = None) -> Dict[str, float]:
        """
        获取指定时间的特征（时间因果安全）
        
        这是唯一的特征读取入口！
        """
        current_clock = self._clock.available_at_ms()

        if self.config.mode == FeatureMode.REPLAY:
            query_time = timestamp_ms
        else:
            query_time = min(timestamp_ms, current_clock)

        snapshot = self._pit_store.get_features_at_time(query_time)
        features = snapshot.features if hasattr(snapshot, 'features') else snapshot

        if feature_names is not None:
            safe_features = {}
            for name in feature_names:
                status = self._availability_guard.check(
                    feature_name=name,
                    feature_timestamp=query_time,
                    query_time=current_clock,
                    clock=self._clock
                )
                
                from domain.feature.availability import AvailabilityStatus
                if status == AvailabilityStatus.AVAILABLE and name in features:
                    safe_features[name] = features[name]
                elif status != AvailabilityStatus.UNKNOWN and status != AvailabilityStatus.PARTIAL_ONLY:
                    logger.warning(f"Feature '{name}' not available at {query_time}: {status.value}")
            
            return safe_features
        
        return features
    
    def create_snapshot(self, timestamp_ms: Optional[int] = None) -> FeatureSnapshot:
        """创建特征快照"""
        if timestamp_ms is None:
            timestamp_ms = now_ms()
        
        features = self.get_features_at(timestamp_ms)
        snapshot_id = f"feature_snapshot_{timestamp_ms}"
        
        immutable_snapshot = create_immutable_snapshot(
            features=features,
            snapshot_id=snapshot_id,
            metadata={
                "symbol": self.config.symbol,
                "mode": self.config.mode.value,
                "timestamp": timestamp_ms
            }
        )
        
        self._snapshot_store.store(immutable_snapshot)
        
        if self._on_snapshot_callback:
            asyncio.create_task(self._on_snapshot_callback(snapshot_id, timestamp_ms))
        
        return FeatureSnapshot(
            snapshot_id=snapshot_id,
            timestamp_ms=timestamp_ms,
            features=features,
            symbol=self.config.symbol
        )
    
    def get_snapshot(self, snapshot_id: str) -> Optional[FeatureSnapshot]:
        """获取快照"""
        snapshot = self._snapshot_store.get(snapshot_id)
        if snapshot:
            return FeatureSnapshot(
                snapshot_id=snapshot_id,
                timestamp_ms=snapshot.metadata.get('timestamp', 0),
                features=snapshot.features,
                symbol=snapshot.metadata.get('symbol', self.config.symbol)
            )
        return None
    
    def get_all_feature_names(self) -> List[str]:
        """获取所有可用特征名称"""
        return list(self._calculator.schemas.keys())
    
    def get_feature_schema(self, feature_name: str) -> Optional[Dict[str, Any]]:
        """获取特征 Schema"""
        schema = self._calculator.schemas.get(feature_name)
        if schema:
            return {
                "name": schema.name,
                "category": schema.category,
                "available_after_periods": schema.available_after_periods,
                "description": schema.description
            }
        return None

    async def on_event(self, event: Any) -> None:
        if isinstance(event, FeatureEvent):
            await self.emit_event(event.event_type, event.data, event.timestamp_ms)
        elif isinstance(event, dict):
            event_type = event.get("event_type", "unknown")
            data = event.get("data", {})
            timestamp_ms = event.get("timestamp_ms")
            await self.emit_event(event_type, data, timestamp_ms)

    async def snapshot(self) -> Dict[str, Any]:
        ts = now_ms()
        features = self.get_features_at(ts)
        return {
            "timestamp_ms": ts,
            "symbol": self.config.symbol,
            "mode": self.config.mode.value,
            "features": features,
            "running": self._running,
        }

    async def recover(self, checkpoint: Any = None) -> None:
        if checkpoint is None:
            return
        if isinstance(checkpoint, dict):
            if "features" in checkpoint:
                ts = checkpoint.get("timestamp_ms", now_ms())
                self._pit_store.store_features_batch(
                    features=checkpoint["features"],
                    feature_timestamp=ts,
                    source_types={k: FeatureSourceType.DERIVED for k in checkpoint["features"]}
                )

    def get_state(self) -> Dict[str, Any]:
        return {
            "feature_availability": self._availability_guard,
            "feature_cache": self._pit_store,
            "feature_pit_index": self._pit_store,
            "symbol": self.config.symbol,
            "mode": self.config.mode.value,
            "running": self._running,
        }
    
    def reset(self):
        """重置 FeatureRuntime 状态 - 用于切换 symbol/mode 时清理旧状态"""
        if hasattr(self, '_pit_store'):
            self._pit_store.clear()
        if hasattr(self, '_calculator'):
            self._calculator._price_buffer.clear()
            self._calculator._volume_buffer.clear()
            self._calculator._high_buffer.clear()
            self._calculator._low_buffer.clear()
            self._calculator._trade_extractor.clear()
            self._calculator._liquidation_extractor.clear()
            self._calculator._oi_funding_correlator.clear()
            self._calculator._trade_buffer.clear()
            self._calculator._liquidation_buffer.clear()
            self._calculator._oi_buffer.clear()
            self._calculator._funding_buffer.clear()
            self._calculator._oi_timestamp_buffer.clear()
        logger.info(f"FeatureRuntime reset for {self.config.symbol}")


# 实例注册表 - 按 (symbol, mode) 键隔离
_feature_runtime_instances = {}


def get_feature_runtime(config: Optional[FeatureConfig] = None) -> FeatureRuntime:
    """
    获取特征运行时（按 symbol/mode 隔离）
    
    每对 (symbol, mode) 会有独立的 FeatureRuntime 实例，
    避免多任务/多 symbol 之间的状态污染。
    """
    config = config or FeatureConfig()
    instance_key = (config.symbol, config.mode.value)
    
    if instance_key not in _feature_runtime_instances:
        _feature_runtime_instances[instance_key] = FeatureRuntime(config)
        logger.info(f"Created new FeatureRuntime instance: {instance_key}")
    else:
        existing_runtime = _feature_runtime_instances[instance_key]
        # 检查现有实例的配置是否匹配
        if existing_runtime.config.mode != config.mode:
            logger.warning(f"Mode mismatch for existing instance {instance_key}, creating new one")
            _feature_runtime_instances[instance_key] = FeatureRuntime(config)
    
    return _feature_runtime_instances[instance_key]


def clear_feature_runtime_cache():
    """清除所有缓存的 FeatureRuntime 实例"""
    global _feature_runtime_instances
    cleared_count = len(_feature_runtime_instances)
    _feature_runtime_instances = {}
    logger.info(f"Cleared {cleared_count} FeatureRuntime instances")


# 禁止直接导出 UnifiedFeatureCalculator！
# 所有特征计算必须通过 FeatureRuntime
__all__ = ["FeatureRuntime", "FeatureConfig", "FeatureEvent", "get_feature_runtime"]
