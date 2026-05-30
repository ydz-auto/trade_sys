from typing import Optional
from collections import deque

from domain.event.protocol import ImmutableEvent
from infrastructure.logging import get_logger

logger = get_logger("runtime.authority.ordering")


class OrderingAuthority:

    def __init__(self, max_history: int = 1000):
        self._last_event_time_ms: Optional[int] = None
        self._last_sequence_number: int = 0
        self._event_history: deque = deque(maxlen=max_history)
        self._max_history = max_history

    @property
    def last_event_time_ms(self) -> Optional[int]:
        return self._last_event_time_ms

    @property
    def last_sequence_number(self) -> int:
        return self._last_sequence_number

    def validate_order(
        self,
        current_event: ImmutableEvent,
    ) -> tuple[bool, Optional[str]]:
        if self._last_event_time_ms is None:
            return True, None

        if current_event.event_time_ms < self._last_event_time_ms:
            error_msg = (
                f"Event ordering violation: "
                f"current_time={current_event.event_time_ms} < "
                f"last_time={self._last_event_time_ms}, "
                f"event_id={current_event.event_id}"
            )
            logger.error(error_msg)
            return False, error_msg

        return True, None

    def assign_sequence_number(
        self,
        event: ImmutableEvent,
    ) -> int:
        self._last_sequence_number += 1

        self._last_event_time_ms = event.event_time_ms

        self._event_history.append({
            "sequence_number": self._last_sequence_number,
            "event_id": event.event_id,
            "event_time_ms": event.event_time_ms,
            "event_type": event.event_type,
        })

        logger.debug(
            f"Assigned sequence number {self._last_sequence_number} "
            f"to event {event.event_id}"
        )

        return self._last_sequence_number

    def process_event(
        self,
        event: ImmutableEvent,
    ) -> tuple[int, Optional[str]]:
        is_valid, error_msg = self.validate_order(event)
        if not is_valid:
            return -1, error_msg

        sequence_number = self.assign_sequence_number(event)

        return sequence_number, None

    def reset(self) -> None:
        self._last_event_time_ms = None
        self._last_sequence_number = 0
        self._event_history.clear()

    def get_history(
        self,
        start_sequence: int = 0,
        end_sequence: Optional[int] = None,
    ) -> list:
        if end_sequence is None:
            end_sequence = self._last_sequence_number

        return [
            record
            for record in self._event_history
            if start_sequence <= record["sequence_number"] <= end_sequence
        ]

    def __repr__(self) -> str:
        return (
            f"OrderingAuthority("
            f"last_time={self._last_event_time_ms}, "
            f"last_seq={self._last_sequence_number}, "
            f"history_size={len(self._event_history)})"
        )
