from typing import Optional

from domain.risk.guards.base_guard import BaseGuard
from domain.event.protocol import ImmutableEvent
import logging

logger = logging.getLogger(__name__)


class OrderingGuard(BaseGuard):
    def __init__(self, enabled: bool = True):
        super().__init__("OrderingGuard", enabled)
        self._last_event_time_ms: Optional[int] = None

    def _before_process_impl(self, event: ImmutableEvent) -> None:
        if self._last_event_time_ms is None:
            self._last_event_time_ms = event.event_time_ms
            return

        if event.event_time_ms < self._last_event_time_ms:
            self._violation(
                f"Event ordering violation: "
                f"current_time={event.event_time_ms} < "
                f"last_time={self._last_event_time_ms}",
                event,
            )

        self._last_event_time_ms = event.event_time_ms

    def reset(self) -> None:
        super().reset()
        self._last_event_time_ms = None

    def __repr__(self) -> str:
        return f"OrderingGuard(enabled={self.enabled}, last_time={self._last_event_time_ms})"
