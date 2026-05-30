from typing import Set

from domain.risk.guards.base_guard import BaseGuard
from domain.event.protocol import ImmutableEvent
import logging

logger = logging.getLogger(__name__)


class DuplicateGuard(BaseGuard):
    def __init__(self, max_history: int = 10000, enabled: bool = True):
        super().__init__("DuplicateGuard", enabled)
        self._processed_ids: Set[str] = set()
        self._max_history = max_history
        self._id_list = []

    def _before_process_impl(self, event: ImmutableEvent) -> None:
        if event.event_id in self._processed_ids:
            self._violation(
                f"Duplicate event: {event.event_id}",
                event,
            )

        self._processed_ids.add(event.event_id)
        self._id_list.append(event.event_id)

        if len(self._id_list) > self._max_history:
            oldest_id = self._id_list.pop(0)
            self._processed_ids.discard(oldest_id)

    def reset(self) -> None:
        super().reset()
        self._processed_ids.clear()
        self._id_list.clear()

    def __repr__(self) -> str:
        return f"DuplicateGuard(enabled={self.enabled}, processed={len(self._processed_ids)})"
