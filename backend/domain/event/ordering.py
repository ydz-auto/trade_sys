"""
Event Ordering Types - 事件排序类型定义

纯 domain 类型，不包含运行时状态管理。
排序引擎（EventOrderingDeterminism）在 runtime/kernel/event/event_ordering.py
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum


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
