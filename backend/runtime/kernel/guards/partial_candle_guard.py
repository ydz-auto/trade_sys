"""
Partial Candle Guard - 未完成 K 线守卫

禁止使用未完成的 K 线
"""

from typing import Any

from runtime.kernel.guards.base_guard import BaseGuard
from domain.event.protocol import ImmutableEvent
import logging

logger = logging.getLogger(__name__)


class PartialCandleGuard(BaseGuard):
    """
    未完成 K 线守卫：禁止使用未完成的 K 线
    
    K 线必须标记为 is_complete=True 才能使用
    """
    
    def __init__(self, enabled: bool = True):
        super().__init__("PartialCandleGuard", enabled)
    
    def _before_process_impl(self, event: ImmutableEvent) -> None:
        """处理前检查：验证 K 线完整性"""
        if event.event_type != "CANDLE":
            # 非 K 线事件，不检查
            return
        
        # 检查 is_complete 标记
        if not event.payload.get("is_complete", True):
            self._violation(
                "Cannot use partial candle: is_complete=False",
                event,
            )
    
    def __repr__(self) -> str:
        return f"PartialCandleGuard(enabled={self.enabled})"
