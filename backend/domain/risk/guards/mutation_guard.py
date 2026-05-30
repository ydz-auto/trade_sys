from domain.risk.guards.base_guard import BaseGuard
from domain.event.protocol import ImmutableEvent
import logging

logger = logging.getLogger(__name__)


class MutationGuard(BaseGuard):
    def __init__(self, enabled: bool = True):
        super().__init__("MutationGuard", enabled)

    def _before_process_impl(self, event: ImmutableEvent) -> None:
        if not event.verify_integrity():
            self._violation(
                "Event integrity verification failed: hash mismatch",
                event,
            )

    def __repr__(self) -> str:
        return f"MutationGuard(enabled={self.enabled})"
