"""
Event Ordering Determinism - 事件排序确定性

核心问题：
当多个事件具有相同的 timestamp 时，处理顺序可能不确定，
导致 Replay 和 Live 的特征生成结果不同。

例如：
- 同一时间戳有多个 trade 事件
- 不同处理顺序导致不同的 VWAP
- Replay 和 Live 顺序可能不同

解决方案：
1. 定义确定性的排序规则
2. 使用次级排序键（如 sequence_number）
3. 确保相同输入总是产生相同输出
"""

from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import hashlib
import json

from infrastructure.logging import get_logger

logger = get_logger("infrastructure.event_ordering")


class EventPriority(Enum):
    """事件优先级"""
    CRITICAL = 0     # 系统事件
    HIGH = 1         # 订单状态更新
    NORMAL = 2       # 行情数据
    LOW = 3          # 统计聚合


@dataclass
class OrderedEvent:
    """有序事件"""
    event_id: str
    event_type: str
    
    primary_key: int          # 主排序键（通常是 timestamp）
    secondary_key: int        # 次排序键（sequence_number）
    tertiary_key: str         # 第三排序键（event_type）
    
    priority: EventPriority
    
    symbol: str
    exchange: str
    
    data: Dict[str, Any]
    
    source_sequence: int = 0  # 原始序列号
    
    def get_sort_key(self) -> Tuple[int, int, str, int]:
        """获取排序键"""
        return (
            self.primary_key,
            self.secondary_key,
            self.tertiary_key,
            self.source_sequence,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "primary_key": self.primary_key,
            "secondary_key": self.secondary_key,
            "tertiary_key": self.tertiary_key,
            "priority": self.priority.value,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "data": self.data,
            "source_sequence": self.source_sequence,
        }


class EventOrderingDeterminism:
    """
    事件排序确定性管理器
    
    核心功能：
    1. 为事件分配确定性的排序键
    2. 确保相同事件集合总是产生相同顺序
    3. 支持多种排序策略
    """
    
    EVENT_TYPE_PRIORITY: Dict[str, EventPriority] = {
        "system": EventPriority.CRITICAL,
        "order_update": EventPriority.HIGH,
        "order_fill": EventPriority.HIGH,
        "position_update": EventPriority.HIGH,
        "balance_update": EventPriority.HIGH,
        "candle": EventPriority.NORMAL,
        "trade": EventPriority.NORMAL,
        "depth": EventPriority.NORMAL,
        "ticker": EventPriority.NORMAL,
        "funding": EventPriority.NORMAL,
        "liquidation": EventPriority.NORMAL,
        "aggregation": EventPriority.LOW,
        "statistics": EventPriority.LOW,
    }
    
    def __init__(self):
        self._sequence_counter = 0
        self._event_buffer: List[OrderedEvent] = []
        self._ordering_log: List[Dict[str, Any]] = []
    
    def create_ordered_event(
        self,
        event_type: str,
        timestamp: int,
        data: Dict[str, Any],
        symbol: str = "",
        exchange: str = "",
        sequence_number: Optional[int] = None,
        event_id: Optional[str] = None,
    ) -> OrderedEvent:
        """
        创建有序事件
        
        Args:
            event_type: 事件类型
            timestamp: 时间戳
            data: 事件数据
            symbol: 品种
            exchange: 交易所
            sequence_number: 序列号（None则自动分配）
            event_id: 事件ID（None则自动生成）
        """
        self._sequence_counter += 1
        
        if sequence_number is None:
            sequence_number = self._sequence_counter
        
        if event_id is None:
            event_id = f"{event_type}_{timestamp}_{sequence_number}"
        
        priority = self.EVENT_TYPE_PRIORITY.get(event_type, EventPriority.NORMAL)
        
        return OrderedEvent(
            event_id=event_id,
            event_type=event_type,
            primary_key=timestamp,
            secondary_key=sequence_number,
            tertiary_key=event_type,
            priority=priority,
            symbol=symbol,
            exchange=exchange,
            data=data,
            source_sequence=self._sequence_counter,
        )
    
    def add_event(self, event: OrderedEvent):
        """添加事件到缓冲区"""
        self._event_buffer.append(event)
    
    def add_events_batch(self, events: List[OrderedEvent]):
        """批量添加事件"""
        self._event_buffer.extend(events)
    
    def sort_events(self, events: Optional[List[OrderedEvent]] = None) -> List[OrderedEvent]:
        """
        排序事件
        
        Args:
            events: 要排序的事件列表（None则使用缓冲区）
        
        Returns:
            List[OrderedEvent]: 排序后的事件列表
        """
        to_sort = events if events is not None else self._event_buffer
        
        sorted_events = sorted(to_sort, key=lambda e: e.get_sort_key())
        
        if events is None:
            self._ordering_log.append({
                "event_count": len(sorted_events),
                "first_event_id": sorted_events[0].event_id if sorted_events else None,
                "last_event_id": sorted_events[-1].event_id if sorted_events else None,
                "timestamp": datetime.utcnow().isoformat(),
            })
        
        return sorted_events
    
    def get_sorted_events(self, clear_buffer: bool = True) -> List[OrderedEvent]:
        """
        获取排序后的事件
        
        Args:
            clear_buffer: 是否清空缓冲区
        """
        sorted_events = self.sort_events()
        
        if clear_buffer:
            self._event_buffer.clear()
        
        return sorted_events
    
    def process_in_order(
        self,
        events: List[OrderedEvent],
        processor: Callable[[OrderedEvent], Any],
    ) -> List[Any]:
        """
        按顺序处理事件
        
        Args:
            events: 事件列表
            processor: 处理函数
        
        Returns:
            List[Any]: 处理结果列表
        """
        sorted_events = self.sort_events(events)
        results = []
        
        for event in sorted_events:
            try:
                result = processor(event)
                results.append(result)
            except Exception as e:
                logger.error(f"Error processing event {event.event_id}: {e}")
                results.append(None)
        
        return results
    
    def verify_ordering_determinism(
        self,
        events: List[OrderedEvent],
        expected_order: List[str],
    ) -> Dict[str, Any]:
        """
        验证排序确定性
        
        Args:
            events: 事件列表
            expected_order: 期望的事件ID顺序
        """
        sorted_events = self.sort_events(events)
        actual_order = [e.event_id for e in sorted_events]
        
        is_deterministic = actual_order == expected_order
        
        return {
            "is_deterministic": is_deterministic,
            "expected_order": expected_order,
            "actual_order": actual_order,
            "mismatch_count": sum(1 for a, b in zip(actual_order, expected_order) if a != b),
        }
    
    def compute_ordering_hash(self, events: List[OrderedEvent]) -> str:
        """
        计算排序哈希
        
        用于验证不同运行的事件顺序是否一致
        """
        sorted_events = self.sort_events(events)
        
        order_data = [e.event_id for e in sorted_events]
        content = json.dumps(order_data, sort_keys=True)
        
        return hashlib.sha256(content.encode()).hexdigest()[:32]
    
    def group_events_by_timestamp(
        self,
        events: List[OrderedEvent],
    ) -> Dict[int, List[OrderedEvent]]:
        """
        按时间戳分组事件
        
        同一时间戳的事件按 secondary_key 排序
        """
        sorted_events = self.sort_events(events)
        
        groups: Dict[int, List[OrderedEvent]] = {}
        
        for event in sorted_events:
            ts = event.primary_key
            if ts not in groups:
                groups[ts] = []
            groups[ts].append(event)
        
        return groups
    
    def get_ordering_stats(self) -> Dict[str, Any]:
        """获取排序统计"""
        return {
            "total_events_processed": self._sequence_counter,
            "buffer_size": len(self._event_buffer),
            "ordering_operations": len(self._ordering_log),
        }
    
    def reset_sequence(self):
        """重置序列计数器"""
        self._sequence_counter = 0
        self._event_buffer.clear()


_ordering_instances: Dict[str, EventOrderingDeterminism] = {}


def get_event_ordering(instance_id: str = "default") -> EventOrderingDeterminism:
    """获取事件排序实例"""
    if instance_id not in _ordering_instances:
        _ordering_instances[instance_id] = EventOrderingDeterminism()
    return _ordering_instances[instance_id]


def create_deterministic_event(
    event_type: str,
    timestamp: int,
    data: Dict[str, Any],
    **kwargs,
) -> OrderedEvent:
    """创建确定性事件的便捷函数"""
    ordering = get_event_ordering()
    return ordering.create_ordered_event(event_type, timestamp, data, **kwargs)
