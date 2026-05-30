"""
Event Ordering Determinism - 事件排序确定性引擎

运行时排序引擎。纯类型定义在 domain/event/ordering.py
"""

from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import hashlib
import json

from infrastructure.logging import get_logger
from domain.event.ordering import EventPriority, OrderedEvent

logger = get_logger("runtime.kernel.event.event_ordering")


class EventOrderingDeterminism:

    EVENT_TYPE_PRIORITY: Dict[str, EventPriority] = {
        "system": EventPriority.CRITICAL,
        "order_update": EventPriority.HIGH,
        "order_fill": EventPriority.HIGH,
        "position_update": EventPriority.HIGH,
        "balance_update": EventPriority.HIGH,
        "candle": EventPriority.NORMAL,
        "trade": EventPriority.NORMAL,
        "depth": EventPriority.NORMAL,
        "ticker": EventPriority.NORMAL,
        "funding": EventPriority.NORMAL,
        "liquidation": EventPriority.NORMAL,
        "aggregation": EventPriority.LOW,
        "statistics": EventPriority.LOW,
    }

    def __init__(self):
        self._sequence_counter = 0
        self._event_buffer: List[OrderedEvent] = []
        self._ordering_log: List[Dict[str, Any]] = []
        self._last_primary_key: int = 0

    def create_ordered_event(
        self,
        event_type: str,
        timestamp: int,
        data: Dict[str, Any],
        symbol: str = "",
        exchange: str = "",
        sequence_number: Optional[int] = None,
        event_id: Optional[str] = None,
    ) -> OrderedEvent:
        self._sequence_counter += 1

        if sequence_number is None:
            sequence_number = self._sequence_counter

        if event_id is None:
            event_id = f"{event_type}_{timestamp}_{sequence_number}"

        priority = self.EVENT_TYPE_PRIORITY.get(event_type, EventPriority.NORMAL)

        return OrderedEvent(
            event_id=event_id,
            event_type=event_type,
            primary_key=timestamp,
            secondary_key=sequence_number,
            tertiary_key=event_type,
            priority=priority,
            symbol=symbol,
            exchange=exchange,
            data=data,
            source_sequence=self._sequence_counter,
        )

    def add_event(self, event: OrderedEvent):
        self._event_buffer.append(event)

    def add_events_batch(self, events: List[OrderedEvent]):
        self._event_buffer.extend(events)

    def sort_events(self, events: Optional[List[OrderedEvent]] = None) -> List[OrderedEvent]:
        to_sort = events if events is not None else self._event_buffer

        sorted_events = sorted(to_sort, key=lambda e: e.get_sort_key())

        if events is None:
            self._ordering_log.append({
                "event_count": len(sorted_events),
                "first_event_id": sorted_events[0].event_id if sorted_events else None,
                "last_event_id": sorted_events[-1].event_id if sorted_events else None,
                "timestamp": datetime.utcnow().isoformat(),
            })

        return sorted_events

    def get_sorted_events(self, clear_buffer: bool = True) -> List[OrderedEvent]:
        sorted_events = self.sort_events()

        if clear_buffer:
            self._event_buffer.clear()

        return sorted_events

    def process_in_order(
        self,
        events: List[OrderedEvent],
        processor: Callable[[OrderedEvent], Any],
    ) -> List[Any]:
        sorted_events = self.sort_events(events)
        results = []

        for event in sorted_events:
            try:
                result = processor(event)
                results.append(result)
            except Exception as e:
                logger.error(f"Error processing event {event.event_id}: {e}")
                results.append(None)

        return results

    def verify_ordering_determinism(
        self,
        events: List[OrderedEvent],
        expected_order: List[str],
    ) -> Dict[str, Any]:
        sorted_events = self.sort_events(events)
        actual_order = [e.event_id for e in sorted_events]

        is_deterministic = actual_order == expected_order

        return {
            "is_deterministic": is_deterministic,
            "expected_order": expected_order,
            "actual_order": actual_order,
            "mismatch_count": sum(1 for a, b in zip(actual_order, expected_order) if a != b),
        }

    def compute_ordering_hash(self, events: List[OrderedEvent]) -> str:
        sorted_events = self.sort_events(events)

        order_data = [e.event_id for e in sorted_events]
        content = json.dumps(order_data, sort_keys=True)

        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def group_events_by_timestamp(
        self,
        events: List[OrderedEvent],
    ) -> Dict[int, List[OrderedEvent]]:
        sorted_events = self.sort_events(events)

        groups: Dict[int, List[OrderedEvent]] = {}

        for event in sorted_events:
            ts = event.primary_key
            if ts not in groups:
                groups[ts] = []
            groups[ts].append(event)

        return groups

    def get_ordering_stats(self) -> Dict[str, Any]:
        return {
            "total_events_processed": self._sequence_counter,
            "buffer_size": len(self._event_buffer),
            "ordering_operations": len(self._ordering_log),
        }

    def validate_event_order(self, event) -> bool:
        if not hasattr(event, 'timestamp') and not hasattr(event, 'primary_key'):
            return True
        event_key = getattr(event, 'timestamp', None) or getattr(event, 'primary_key', 0)
        if isinstance(event_key, (int, float)):
            if event_key < self._last_primary_key:
                return False
            self._last_primary_key = event_key
        return True

    def reset_sequence(self):
        self._sequence_counter = 0
        self._event_buffer.clear()


_ordering_instances: Dict[str, EventOrderingDeterminism] = {}


def get_event_ordering(instance_id: str = "default") -> EventOrderingDeterminism:
    if instance_id not in _ordering_instances:
        _ordering_instances[instance_id] = EventOrderingDeterminism()
    return _ordering_instances[instance_id]


def create_deterministic_event(
    event_type: str,
    timestamp: int,
    data: Dict[str, Any],
    **kwargs,
) -> OrderedEvent:
    ordering = get_event_ordering()
    return ordering.create_ordered_event(event_type, timestamp, data, **kwargs)
