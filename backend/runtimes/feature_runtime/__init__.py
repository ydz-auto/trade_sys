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
    真正的特征运行时（单一实现入口）
    
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
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, config: Optional[FeatureConfig] = None):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
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
        
        self._initialized = True
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
        # 1. 时间因果检查
        if event.timestamp_ms > self._clock.available_at_ms():
            logger.warning(f"Event time {event.timestamp_ms} ahead of clock!")
            return
        
        # 2. 根据事件类型处理
        if event.event_type == "kline":
            await self._process_kline_event(event)
        elif event.event_type == "trade":
            await self._process_trade_event(event)
        elif event.event_type == "orderbook":
            await self._process_orderbook_event(event)
        
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
            source_types={feat: FeatureSourceType.CALCULATED for feat in features}
        )
        
        # 3. 触发回调
        if self._on_feature_callback:
            await self._on_feature_callback(event.timestamp_ms, features)
    
    async def _process_trade_event(self, event: FeatureEvent):
        """处理交易事件"""
        # 交易事件可以用来计算成交量相关特征
        data = event.data
        symbol = data.get('symbol', self.config.symbol)
        price = float(data.get('price', 0))
        volume = float(data.get('volume', 0))
        
        # 更新 PIT Store（交易级数据）
        self._pit_store.store_features_batch(
            features={
                'trade_price': price,
                'trade_volume': volume
            },
            feature_timestamp=event.timestamp_ms,
            source_types={
                'trade_price': FeatureSourceType.RAW,
                'trade_volume': FeatureSourceType.RAW
            }
        )
    
    async def _process_orderbook_event(self, event: FeatureEvent):
        """处理订单簿事件"""
        data = event.data
        symbol = data.get('symbol', self.config.symbol)
        
        # 存储订单簿数据到 PIT Store
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
        # 1. 时间因果检查
        current_clock = self._clock.available_at_ms()
        safe_timestamp = min(timestamp_ms, current_clock)
        
        # 2. 从 PIT Store 获取
        snapshot = self._pit_store.get_features_at_time(safe_timestamp)
        features = snapshot.features if hasattr(snapshot, 'features') else snapshot
        
        # 3. 检查特征可用性
        if feature_names is not None:
            safe_features = {}
            for name in feature_names:
                status = self._availability_guard.check(
                    feature_name=name,
                    feature_timestamp=safe_timestamp,
                    query_time=current_clock,
                    clock=self._clock
                )
                
                from domain.feature.availability import AvailabilityStatus
                if status == AvailabilityStatus.AVAILABLE and name in features:
                    safe_features[name] = features[name]
                elif status != AvailabilityStatus.UNKNOWN and status != AvailabilityStatus.PARTIAL_ONLY:
                    logger.warning(f"Feature '{name}' not available at {safe_timestamp}: {status.value}")
            
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
                    source_types={k: FeatureSourceType.CALCULATED for k in checkpoint["features"]}
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


# 全局实例
def get_feature_runtime(config: Optional[FeatureConfig] = None) -> FeatureRuntime:
    """获取特征运行时（单一实例）"""
    return FeatureRuntime(config)


# 禁止直接导出 UnifiedFeatureCalculator！
# 所有特征计算必须通过 FeatureRuntime
__all__ = ["FeatureRuntime", "FeatureConfig", "FeatureEvent", "get_feature_runtime"]
