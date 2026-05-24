"""
Unified Event Processor - 统一事件处理器

核心问题：
Replay Runtime 和 Live Runtime 的事件处理逻辑不一致，
导致特征生成结果不同。

解决方案：
1. 定义统一的 EventProcessor 接口
2. Replay 和 Live 使用相同的处理逻辑
3. 通过 EventTimeManager 统一时间语义
4. 确保特征生成的确定性
"""

from typing import Dict, List, Optional, Any, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
from abc import ABC, abstractmethod
import asyncio
import hashlib
import json

from infrastructure.logging import get_logger
from domain.event.infrastructure.event_time import (
    EventTimeManager,
    EventTimeRecord,
    EventSource,
    get_event_time_manager,
)
from domain.feature.infrastructure.partial_candle_handler import (
    PartialCandleHandler,
    get_partial_candle_handler,
)
from infrastructure.storage.point_in_time_store import (
    PointInTimeFeatureStore,
    get_point_in_time_store,
)

logger = get_logger("domain.event.infrastructure.unified_event_processor")


@dataclass
class EventContext:
    """事件上下文"""
    event_id: str
    event_type: str
    symbol: str
    exchange: str
    
    exchange_time: int
    receive_time: int
    available_at: int
    
    source: EventSource
    
    data: Dict[str, Any]
    
    replay_clock: int = 0
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_hash(self) -> str:
        """获取事件哈希（用于确定性验证）"""
        content = json.dumps({
            "event_id": self.event_id,
            "event_type": self.event_type,
            "symbol": self.symbol,
            "exchange_time": self.exchange_time,
            "data": self.data,
        }, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class ProcessingResult:
    """处理结果"""
    event_id: str
    success: bool
    
    features: Dict[str, Any]
    feature_timestamps: Dict[str, int]
    available_at_times: Dict[str, int]
    
    blocked_features: List[str]
    warnings: List[str]
    
    processing_time_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "success": self.success,
            "feature_count": len(self.features),
            "blocked_count": len(self.blocked_features),
            "warning_count": len(self.warnings),
            "processing_time_ms": self.processing_time_ms,
        }


class EventProcessor(ABC):
    """事件处理器抽象基类"""
    
    @abstractmethod
    async def process(self, context: EventContext) -> ProcessingResult:
        """处理事件"""
        pass
    
    @abstractmethod
    def get_processor_name(self) -> str:
        """获取处理器名称"""
        pass


class UnifiedEventProcessor:
    """
    统一事件处理器
    
    确保 Replay 和 Live 使用完全相同的处理逻辑
    """
    
    def __init__(
        self,
        symbol: str,
        interval_ms: int = 60000,
    ):
        self.symbol = symbol
        self.interval_ms = interval_ms
        
        self.event_time_manager = get_event_time_manager()
        self.partial_candle_handler = get_partial_candle_handler()
        self.feature_store = get_point_in_time_store(symbol, interval_ms)
        
        self._processors: Dict[str, EventProcessor] = {}
        self._pre_hooks: List[Callable[[EventContext], Awaitable[None]]] = []
        self._post_hooks: List[Callable[[EventContext, ProcessingResult], Awaitable[None]]] = []
        
        self._processing_stats = {
            "total_events": 0,
            "successful_events": 0,
            "failed_events": 0,
            "total_processing_time_ms": 0.0,
        }
    
    def register_processor(self, event_type: str, processor: EventProcessor):
        """注册事件处理器"""
        self._processors[event_type] = processor
        logger.info(f"Registered processor for event_type={event_type}: {processor.get_processor_name()}")
    
    def add_pre_hook(self, hook: Callable[[EventContext], Awaitable[None]]):
        """添加前置钩子"""
        self._pre_hooks.append(hook)
    
    def add_post_hook(self, hook: Callable[[EventContext, ProcessingResult], Awaitable[None]]):
        """添加后置钩子"""
        self._post_hooks.append(hook)
    
    async def process_event(
        self,
        event_type: str,
        data: Dict[str, Any],
        exchange_time: int,
        receive_time: Optional[int] = None,
        source: EventSource = EventSource.EXCHANGE,
        replay_clock: Optional[int] = None,
    ) -> ProcessingResult:
        """
        处理事件（统一入口）
        
        Args:
            event_type: 事件类型
            data: 事件数据
            exchange_time: 交易所时间
            receive_time: 接收时间
            source: 事件来源
            replay_clock: 回放时钟（用于 Replay 场景）
        """
        import time
        start_time = time.time()
        
        event_id = f"{event_type}_{exchange_time}_{hash(str(data)) % 10000}"
        
        if receive_time is None:
            receive_time = int(datetime.utcnow().timestamp() * 1000)
        
        if replay_clock is None:
            replay_clock = receive_time
        
        event_time_record = self.event_time_manager.record_event(
            event_id=event_id,
            event_type=event_type,
            exchange_time=exchange_time,
            receive_time=receive_time,
            source=source,
            symbol=self.symbol,
        )
        
        context = EventContext(
            event_id=event_id,
            event_type=event_type,
            symbol=self.symbol,
            exchange=data.get("exchange", "binance"),
            exchange_time=exchange_time,
            receive_time=receive_time,
            available_at=event_time_record.available_at,
            source=source,
            data=data,
            replay_clock=replay_clock,
        )
        
        for hook in self._pre_hooks:
            try:
                await hook(context)
            except Exception as e:
                logger.warning(f"Pre-hook error: {e}")
        
        processor = self._processors.get(event_type)
        
        if processor is None:
            result = ProcessingResult(
                event_id=event_id,
                success=False,
                features={},
                feature_timestamps={},
                available_at_times={},
                blocked_features=[],
                warnings=[f"No processor registered for event_type={event_type}"],
            )
        else:
            try:
                result = await processor.process(context)
                
                if result.features:
                    self.feature_store.store_features_batch(
                        features=result.features,
                        feature_timestamp=exchange_time,
                    )
                
            except Exception as e:
                logger.error(f"Processor error for {event_type}: {e}")
                result = ProcessingResult(
                    event_id=event_id,
                    success=False,
                    features={},
                    feature_timestamps={},
                    available_at_times={},
                    blocked_features=[],
                    warnings=[str(e)],
                )
        
        for hook in self._post_hooks:
            try:
                await hook(context, result)
            except Exception as e:
                logger.warning(f"Post-hook error: {e}")
        
        processing_time_ms = (time.time() - start_time) * 1000
        result.processing_time_ms = processing_time_ms
        
        self._update_stats(result, processing_time_ms)
        
        return result
    
    def get_features_at_time(self, query_time: int) -> Dict[str, Any]:
        """获取指定时间点的特征"""
        snapshot = self.feature_store.get_features_at_time(query_time)
        return snapshot.features
    
    def _update_stats(self, result: ProcessingResult, processing_time_ms: float):
        """更新统计"""
        self._processing_stats["total_events"] += 1
        self._processing_stats["total_processing_time_ms"] += processing_time_ms
        
        if result.success:
            self._processing_stats["successful_events"] += 1
        else:
            self._processing_stats["failed_events"] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self._processing_stats.copy()
        
        if stats["total_events"] > 0:
            stats["success_rate"] = stats["successful_events"] / stats["total_events"]
            stats["avg_processing_time_ms"] = stats["total_processing_time_ms"] / stats["total_events"]
        else:
            stats["success_rate"] = 0.0
            stats["avg_processing_time_ms"] = 0.0
        
        return stats


class CandleEventProcessor(EventProcessor):
    """K线事件处理器"""
    
    def __init__(
        self,
        feature_extractors: Optional[List[Any]] = None,
    ):
        self.feature_extractors = feature_extractors or []
    
    async def process(self, context: EventContext) -> ProcessingResult:
        """处理K线事件"""
        data = context.data
        
        features = {}
        feature_timestamps = {}
        available_at_times = {}
        blocked_features = []
        warnings = []
        
        for extractor in self.feature_extractors:
            try:
                extracted = extractor.extract(data, context.exchange_time)
                
                for name, value in extracted.items():
                    if name in ["timestamp", "symbol", "exchange", "datetime"]:
                        continue
                    
                    features[name] = value
                    feature_timestamps[name] = context.exchange_time
                    available_at_times[name] = context.available_at
            
            except Exception as e:
                warnings.append(f"Extractor {extractor.__class__.__name__} error: {e}")
        
        return ProcessingResult(
            event_id=context.event_id,
            success=True,
            features=features,
            feature_timestamps=feature_timestamps,
            available_at_times=available_at_times,
            blocked_features=blocked_features,
            warnings=warnings,
        )
    
    def get_processor_name(self) -> str:
        return "CandleEventProcessor"


class TradeEventProcessor(EventProcessor):
    """交易事件处理器"""
    
    def __init__(self, trade_feature_extractor: Optional[Any] = None):
        self.trade_feature_extractor = trade_feature_extractor
    
    async def process(self, context: EventContext) -> ProcessingResult:
        """处理交易事件"""
        data = context.data
        
        features = {}
        feature_timestamps = {}
        available_at_times = {}
        blocked_features = []
        warnings = []
        
        if self.trade_feature_extractor:
            try:
                extracted = self.trade_feature_extractor.extract(data, context.exchange_time)
                
                for name, value in extracted.items():
                    if name in ["timestamp", "symbol", "exchange", "datetime"]:
                        continue
                    
                    features[name] = value
                    feature_timestamps[name] = context.exchange_time
                    available_at_times[name] = context.available_at
            
            except Exception as e:
                warnings.append(f"Trade extractor error: {e}")
        
        return ProcessingResult(
            event_id=context.event_id,
            success=True,
            features=features,
            feature_timestamps=feature_timestamps,
            available_at_times=available_at_times,
            blocked_features=blocked_features,
            warnings=warnings,
        )
    
    def get_processor_name(self) -> str:
        return "TradeEventProcessor"


_processor_instances: Dict[str, UnifiedEventProcessor] = {}


def get_unified_event_processor(
    symbol: str,
    interval_ms: int = 60000,
) -> UnifiedEventProcessor:
    """获取统一事件处理器实例"""
    key = f"{symbol}_{interval_ms}"
    if key not in _processor_instances:
        _processor_instances[key] = UnifiedEventProcessor(symbol, interval_ms)
    return _processor_instances[key]
