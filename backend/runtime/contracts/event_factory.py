from typing import Dict, Any

from domain.event.protocol import ImmutableEvent, EventSource, create_event


def create_replay_event(
    event_type: str,
    symbol: str,
    exchange: str,
    event_time_ms: int,
    payload: Dict[str, Any],
    replay_clock_ms: int,
    network_delay_ms: int = 100,
    processing_delay_ms: int = 50,
) -> ImmutableEvent:
    available_time_ms = event_time_ms + network_delay_ms + processing_delay_ms

    return create_event(
        event_type=event_type,
        symbol=symbol,
        exchange=exchange,
        event_time_ms=event_time_ms,
        payload=payload,
        available_time_ms=available_time_ms,
        processing_time_ms=replay_clock_ms,
        source=EventSource.REPLAY,
    )


def create_live_event(
    event_type: str,
    symbol: str,
    exchange: str,
    event_time_ms: int,
    payload: Dict[str, Any],
    processing_delay_ms: int = 50,
) -> ImmutableEvent:
    import time
    processing_time_ms = int(time.time() * 1000)
    available_time_ms = event_time_ms + processing_delay_ms

    return create_event(
        event_type=event_type,
        symbol=symbol,
        exchange=exchange,
        event_time_ms=event_time_ms,
        payload=payload,
        available_time_ms=available_time_ms,
        processing_time_ms=processing_time_ms,
        source=EventSource.LIVE,
    )
