"""
Duplicate Guard - 重复事件守卫

防止重复事件被处理
"""

from typing import Set

from runtime.guards.base_guard import BaseGuard
from domain.event.protocol import ImmutableEvent
from domain.logging import get_logger

logger = get_logger("runtime.guards.duplicate")


class DuplicateGuard(BaseGuard):
    """
    重复事件守卫：防止重复事件被处理
    
    维护一个已处理事件的集合
    """
    
    def __init__(self, max_history: int = 10000, enabled: bool = True):
        super().__init__("DuplicateGuard", enabled)
        self._processed_ids: Set[str] = set()
        self._max_history = max_history
        self._id_list = []
    
    def _before_process_impl(self, event: ImmutableEvent) -> None:
        """处理前检查：验证是否重复"""
        if event.event_id in self._processed_ids:
            self._violation(
                f"Duplicate event: {event.event_id}",
                event,
            )
        
        # 添加到已处理集合
        self._processed_ids.add(event.event_id)
        self._id_list.append(event.event_id)
        
        # 限制大小
        if len(self._id_list) > self._max_history:
            oldest_id = self._id_list.pop(0)
            self._processed_ids.discard(oldest_id)
    
    def reset(self) -> None:
        """重置状态"""
        super().reset()
        self._processed_ids.clear()
        self._id_list.clear()
    
    def __repr__(self) -> str:
        return f"DuplicateGuard(enabled={self.enabled}, processed={len(self._processed_ids)})"
