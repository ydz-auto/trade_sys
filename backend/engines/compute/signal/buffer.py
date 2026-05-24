from datetime import datetime, timedelta
from collections import deque
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EventBufferItem:
    event: Any
    expires_at: datetime

    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at


class EventBuffer:
    def __init__(self, window_seconds: int = 300):
        self.window = timedelta(seconds=window_seconds)
        self._buffer: deque[EventBufferItem] = deque()

    def add(self, event: Any) -> None:
        expires_at = datetime.utcnow() + self.window
        self._buffer.append(EventBufferItem(event=event, expires_at=expires_at))

    def get_valid(self) -> list[Any]:
        self._cleanup()
        return [item.event for item in self._buffer]

    def get_valid_items(self) -> list[EventBufferItem]:
        self._cleanup()
        return list(self._buffer)

    def _cleanup(self) -> None:
        now = datetime.utcnow()
        while self._buffer and self._buffer[0].is_expired():
            self._buffer.popleft()

    def clear(self) -> None:
        self._buffer.clear()

    def __len__(self) -> int:
        self._cleanup()
        return len(self._buffer)

    @property
    def is_empty(self) -> bool:
        return len(self) == 0
