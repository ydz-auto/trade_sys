from typing import Optional, Callable

from domain.risk.guards.base_guard import BaseGuard
from domain.event.protocol import ImmutableEvent
import logging

logger = logging.getLogger(__name__)


class AvailabilityGuard(BaseGuard):
    def __init__(
        self,
        clock_source: Callable[[], int],
        enabled: bool = True,
    ):
        super().__init__("AvailabilityGuard", enabled)
        self._clock_source = clock_source

    def _before_process_impl(self, event: ImmutableEvent) -> None:
        clock_time = self._clock_source()

        if event.available_time_ms > clock_time:
            self._violation(
                f"Event not available: available_time={event.available_time_ms} > "
                f"clock_time={clock_time}",
                event,
            )

    def __repr__(self) -> str:
        return f"AvailabilityGuard(enabled={self.enabled})"
