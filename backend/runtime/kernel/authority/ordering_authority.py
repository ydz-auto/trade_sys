"""
Ordering Authority - 顺序权威

设计原则：
- 不允许任何组件乱序发布事件
- 保证事件因果顺序
- 分配全局序列号
"""

from typing import Optional
from collections import deque

from domain.event.protocol import ImmutableEvent
from infrastructure.logging import get_logger

logger = get_logger("runtime.authority.ordering")


class OrderingAuthority:
    """
    顺序权威：保证事件因果顺序
    
    不允许任何组件乱序发布事件
    """
    
    def __init__(self, max_history: int = 1000):
        self._last_event_time_ms: Optional[int] = None
        self._last_sequence_number: int = 0
        self._event_history: deque = deque(maxlen=max_history)
        self._max_history = max_history
    
    @property
    def last_event_time_ms(self) -> Optional[int]:
        """最后一个事件的时间"""
        return self._last_event_time_ms
    
    @property
    def last_sequence_number(self) -> int:
        """最后一个序列号"""
        return self._last_sequence_number
    
    def validate_order(
        self,
        current_event: ImmutableEvent,
    ) -> tuple[bool, Optional[str]]:
        """
        验证顺序
        
        Args:
            current_event: 当前事件
        
        Returns:
            (是否通过, 问题描述)
        """
        if self._last_event_time_ms is None:
            # 第一个事件，不验证
            return True, None
        
        if current_event.event_time_ms < self._last_event_time_ms:
            error_msg = (
                f"Event ordering violation: "
                f"current_time={current_event.event_time_ms} < "
                f"last_time={self._last_event_time_ms}, "
                f"event_id={current_event.event_id}"
            )
            logger.error(error_msg)
            return False, error_msg
        
        return True, None
    
    def assign_sequence_number(
        self,
        event: ImmutableEvent,
    ) -> int:
        """
        分配全局序列号
        
        Args:
            event: 事件
        
        Returns:
            全局序列号
        """
        self._last_sequence_number += 1
        
        # 更新最后时间
        self._last_event_time_ms = event.event_time_ms
        
        # 记录历史
        self._event_history.append({
            "sequence_number": self._last_sequence_number,
            "event_id": event.event_id,
            "event_time_ms": event.event_time_ms,
            "event_type": event.event_type,
        })
        
        logger.debug(
            f"Assigned sequence number {self._last_sequence_number} "
            f"to event {event.event_id}"
        )
        
        return self._last_sequence_number
    
    def process_event(
        self,
        event: ImmutableEvent,
    ) -> tuple[int, Optional[str]]:
        """
        处理事件：验证顺序 + 分配序列号
        
        Args:
            event: 事件
        
        Returns:
            (序列号, 错误信息)
        """
        # 1. 验证顺序
        is_valid, error_msg = self.validate_order(event)
        if not is_valid:
            return -1, error_msg
        
        # 2. 分配序列号
        sequence_number = self.assign_sequence_number(event)
        
        return sequence_number, None
    
    def reset(self) -> None:
        """重置状态（用于测试）"""
        self._last_event_time_ms = None
        self._last_sequence_number = 0
        self._event_history.clear()
    
    def get_history(
        self,
        start_sequence: int = 0,
        end_sequence: Optional[int] = None,
    ) -> list:
        """
        获取历史记录
        
        Args:
            start_sequence: 起始序列号
            end_sequence: 结束序列号
        
        Returns:
            历史记录列表
        """
        if end_sequence is None:
            end_sequence = self._last_sequence_number
        
        return [
            record
            for record in self._event_history
            if start_sequence <= record["sequence_number"] <= end_sequence
        ]
    
    def __repr__(self) -> str:
        return (
            f"OrderingAuthority("
            f"last_time={self._last_event_time_ms}, "
            f"last_seq={self._last_sequence_number}, "
            f"history_size={len(self._event_history)})"
        )
