"""
Ordering Guard - 顺序守卫

禁止乱序事件，保证因果顺序
"""

from typing import Optional

from runtime.kernel.guards.base_guard import BaseGuard
from domain.event.protocol import ImmutableEvent
import logging

logger = logging.getLogger(__name__)


class OrderingGuard(BaseGuard):
    """
    顺序守卫：禁止乱序事件
    
    保证事件因果顺序，event_time 必须单调递增
    """
    
    def __init__(self, enabled: bool = True):
        super().__init__("OrderingGuard", enabled)
        self._last_event_time_ms: Optional[int] = None
    
    def _before_process_impl(self, event: ImmutableEvent) -> None:
        """处理前检查：验证顺序"""
        if self._last_event_time_ms is None:
            # 第一个事件
            self._last_event_time_ms = event.event_time_ms
            return
        
        if event.event_time_ms < self._last_event_time_ms:
            self._violation(
                f"Event ordering violation: "
                f"current_time={event.event_time_ms} < "
                f"last_time={self._last_event_time_ms}",
                event,
            )
        
        # 更新最后时间
        self._last_event_time_ms = event.event_time_ms
    
    def reset(self) -> None:
        """重置状态"""
        super().reset()
        self._last_event_time_ms = None
    
    def __repr__(self) -> str:
        return f"OrderingGuard(enabled={self.enabled}, last_time={self._last_event_time_ms})"
