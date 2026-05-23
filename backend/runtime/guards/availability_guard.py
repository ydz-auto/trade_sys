"""
Availability Guard - 可用性守卫

禁止未来数据，只允许使用 available_time <= clock_time 的事件
"""

from typing import Optional, Callable

from runtime.guards.base_guard import BaseGuard
from domain.event.protocol import ImmutableEvent
from domain.logging import get_logger

logger = get_logger("runtime.guards.availability")


class AvailabilityGuard(BaseGuard):
    """
    可用性守卫：禁止未来数据
    
    只允许使用 available_time <= clock_time 的事件
    """
    
    def __init__(
        self,
        clock_source: Callable[[], int],
        enabled: bool = True,
    ):
        super().__init__("AvailabilityGuard", enabled)
        self._clock_source = clock_source
    
    def _before_process_impl(self, event: ImmutableEvent) -> None:
        """处理前检查：验证可用性"""
        clock_time = self._clock_source()
        
        if event.available_time_ms > clock_time:
            self._violation(
                f"Event not available: available_time={event.available_time_ms} > "
                f"clock_time={clock_time}",
                event,
            )
    
    def __repr__(self) -> str:
        return f"AvailabilityGuard(enabled={self.enabled})"
