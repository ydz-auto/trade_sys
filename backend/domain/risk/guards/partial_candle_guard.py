from typing import Any

from domain.risk.guards.base_guard import BaseGuard
from domain.event.protocol import ImmutableEvent
import logging

logger = logging.getLogger(__name__)


class PartialCandleGuard(BaseGuard):
    def __init__(self, enabled: bool = True):
        super().__init__("PartialCandleGuard", enabled)

    def _before_process_impl(self, event: ImmutableEvent) -> None:
        if event.event_type != "CANDLE":
            return

        if not event.payload.get("is_complete", True):
            self._violation(
                "Cannot use partial candle: is_complete=False",
                event,
            )

    def __repr__(self) -> str:
        return f"PartialCandleGuard(enabled={self.enabled})"
