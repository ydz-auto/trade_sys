from datetime import datetime
from typing import List, Optional, Any
from dataclasses import dataclass, field

from infrastructure.utilities.runtime_clock import now_ms


@dataclass
class EventBufferItem:
    event: Any
    added_at_ms: int = field(default_factory=lambda: now_ms())

    def is_expired(self, window_ms: int) -> bool:
        return (now_ms() - self.added_at_ms) > window_ms


class EventBuffer:
    def __init__(self, window_seconds: int = 300):
        self._window_ms = window_seconds * 1000
        self._items: List[EventBufferItem] = []

    def add(self, event: Any) -> None:
        self._items.append(EventBufferItem(event=event))
        self._evict_expired()

    def get_valid(self) -> List[Any]:
        self._evict_expired()
        return [item.event for item in self._items]

    def clear(self) -> None:
        self._items.clear()

    def _evict_expired(self) -> None:
        self._items = [item for item in self._items if not item.is_expired(self._window_ms)]

    def __len__(self) -> int:
        self._evict_expired()
        return len(self._items)
