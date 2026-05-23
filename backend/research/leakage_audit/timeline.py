
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Optional, Any


class EventType(Enum):
    FEATURE_AVAILABLE = "feature_available"
    SIGNAL_GENERATED = "signal_generated"
    ORDER_SUBMITTED = "order_submitted"
    FILL_RECEIVED = "fill_received"


@dataclass
class TimelineEvent:
    event_type: EventType
    event_id: str
    timestamp_ms: int
    source: str
    symbol: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class AvailabilityTimeline:
    def __init__(self):
        self.events: List[TimelineEvent] = []
        self._events_by_id: Dict[str, TimelineEvent] = {}

    def add_event(self, event: TimelineEvent) -> None:
        self.events.append(event)
        self._events_by_id[event.event_id] = event

    def add_feature_available(
        self,
        feature_name: str,
        timestamp_ms: int,
        symbol: str,
        availability_delay_ms: Optional[int] = None,
    ) -> str:
        evt = TimelineEvent(
            event_type=EventType.FEATURE_AVAILABLE,
            event_id=f"feat_{feature_name}_{timestamp_ms}",
            timestamp_ms=timestamp_ms,
            source="feature_runtime",
            symbol=symbol,
            metadata={
                "feature_name": feature_name,
                "availability_delay_ms": availability_delay_ms or 0,
            },
        )
        self.add_event(evt)
        return evt.event_id

    def add_signal_generated(
        self,
        signal_name: str,
        timestamp_ms: int,
        symbol: str,
        parent_feature_ids: Optional[List[str]] = None,
    ) -> str:
        evt = TimelineEvent(
            event_type=EventType.SIGNAL_GENERATED,
            event_id=f"sig_{signal_name}_{timestamp_ms}",
            timestamp_ms=timestamp_ms,
            source="signal_runtime",
            symbol=symbol,
            metadata={
                "signal_name": signal_name,
                "parent_feature_ids": parent_feature_ids or [],
            },
        )
        self.add_event(evt)
        return evt.event_id

    def add_order_submitted(
        self,
        order_id: str,
        timestamp_ms: int,
        symbol: str,
        signal_id: Optional[str] = None,
    ) -> str:
        evt = TimelineEvent(
            event_type=EventType.ORDER_SUBMITTED,
            event_id=f"order_{order_id}",
            timestamp_ms=timestamp_ms,
            source="execution_runtime",
            symbol=symbol,
            metadata={
                "order_id": order_id,
                "signal_id": signal_id,
            },
        )
        self.add_event(evt)
        return evt.event_id

    def add_fill_received(
        self,
        fill_id: str,
        timestamp_ms: int,
        symbol: str,
        order_id: str,
    ) -> str:
        evt = TimelineEvent(
            event_type=EventType.FILL_RECEIVED,
            event_id=f"fill_{fill_id}",
            timestamp_ms=timestamp_ms,
            source="execution_runtime",
            symbol=symbol,
            metadata={
                "fill_id": fill_id,
                "order_id": order_id,
            },
        )
        self.add_event(evt)
        return evt.event_id

    def get_event_by_id(self, event_id: str) -> Optional[TimelineEvent]:
        return self._events_by_id.get(event_id)

    def get_events_by_type(self, event_type: EventType) -> List[TimelineEvent]:
        return [e for e in self.events if e.event_type == event_type]

    def get_events_by_symbol(self, symbol: str) -> List[TimelineEvent]:
        return [e for e in self.events if e.symbol == symbol]

    def sort_by_time(self) -> List[TimelineEvent]:
        return sorted(self.events, key=lambda e: e.timestamp_ms)
