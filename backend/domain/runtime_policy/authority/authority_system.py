from typing import Dict, Optional, Tuple, Any

from domain.runtime_policy.authority.clock_authority import ClockAuthority, ClockMode
from domain.runtime_policy.authority.availability_authority import (
    AvailabilityAuthority,
    LatencyModel,
)
from domain.runtime_policy.authority.ordering_authority import OrderingAuthority
from domain.event.protocol import (
    ImmutableEvent,
    ImmutableEventBuilder,
    EventSource,
)
import logging

logger = logging.getLogger(__name__)


class AuthoritySystem:

    def __init__(
        self,
        clock_mode: ClockMode = ClockMode.LIVE,
        latency_model: Optional[LatencyModel] = None,
    ):
        self.clock = ClockAuthority(clock_mode)
        self.availability = AvailabilityAuthority(latency_model)
        self.ordering = OrderingAuthority()

        logger.info("AuthoritySystem initialized")

    def process_raw_event(
        self,
        event_type: str,
        symbol: str,
        exchange: str,
        event_time_ms: int,
        payload: Dict[str, Any],
        source: EventSource = EventSource.LIVE,
    ) -> Tuple[ImmutableEvent, int]:
        processing_time_ms = self.clock.now_ms()

        available_time_ms = self.availability.compute_available_time(
            event_time_ms=event_time_ms,
            event_type=event_type,
        )

        event_id = f"{event_type}_{symbol}_{event_time_ms}"

        builder = ImmutableEventBuilder()
        event = (
            builder
            .event_id(event_id)
            .event_type(event_type)
            .symbol(symbol)
            .exchange(exchange)
            .event_time_ms(event_time_ms)
            .available_time_ms(available_time_ms)
            .processing_time_ms(processing_time_ms)
            .payload(payload)
            .source(source)
            .build()
        )

        sequence_number, error_msg = self.ordering.process_event(event)
        if error_msg:
            raise ValueError(f"Ordering validation failed: {error_msg}")

        logger.debug(
            f"Processed event: {event.event_id}, "
            f"seq={sequence_number}, "
            f"event_time={event.event_time_ms}, "
            f"available_time={event.available_time_ms}, "
            f"processing_time={event.processing_time_ms}"
        )

        return event, sequence_number

    def validate_event(
        self,
        event: ImmutableEvent,
    ) -> Tuple[bool, Optional[str]]:
        if not event.verify_integrity():
            return False, "Event integrity verification failed"

        is_available, error_msg = self.availability.validate_availability(
            available_time_ms=event.available_time_ms,
            clock_ms=self.clock.now_ms(),
            event_id=event.event_id,
        )
        if not is_available:
            return False, error_msg

        is_ordered, error_msg = self.ordering.validate_order(event)
        if not is_ordered:
            return False, error_msg

        return True, None

    def switch_to_replay_mode(self, start_time_ms: int) -> None:
        self.clock.switch_to_replay_mode(start_time_ms)
        self.ordering.reset()

    def switch_to_live_mode(self) -> None:
        self.clock.switch_to_live_mode()
        self.ordering.reset()

    def advance_clock(self, target_ms: int) -> None:
        self.clock.advance_to(target_ms)

    def __repr__(self) -> str:
        return (
            f"AuthoritySystem("
            f"clock={self.clock}, "
            f"availability={self.availability}, "
            f"ordering={self.ordering})"
        )
