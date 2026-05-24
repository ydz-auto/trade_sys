"""
Mutation Guard - 变更守卫

禁止事件被修改，验证完整性哈希
"""

from runtime.kernel.guards.base_guard import BaseGuard
from domain.event.protocol import ImmutableEvent
import logging

logger = logging.getLogger(__name__)


class MutationGuard(BaseGuard):
    """
    变更守卫：禁止事件被修改
    
    验证完整性哈希，确保事件没有被篡改
    """
    
    def __init__(self, enabled: bool = True):
        super().__init__("MutationGuard", enabled)
    
    def _before_process_impl(self, event: ImmutableEvent) -> None:
        """处理前检查：验证完整性"""
        if not event.verify_integrity():
            self._violation(
                "Event integrity verification failed: hash mismatch",
                event,
            )
    
    def __repr__(self) -> str:
        return f"MutationGuard(enabled={self.enabled})"
