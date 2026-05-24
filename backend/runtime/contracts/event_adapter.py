from __future__ import annotations

from typing import Any, Mapping, Union

from domain.event.protocol import EventSource as DomainEventSource
from domain.event.protocol import FrozenDict, ImmutableEvent
from infrastructure.messaging.schema.base_event import BaseEvent
from infrastructure.messaging.event_registry import get_event_class


DEFAULT_EXCHANGE = "unknown"


def _domain_source_to_runtime(source: DomainEventSource) -> str:
    if source == DomainEventSource.REPLAY:
        return "replay_runtime"
    if source == DomainEventSource.PAPER:
        return "paper_runtime"
    if source == DomainEventSource.HISTORICAL:
        return "historical_runtime"
    return "ingestion_runtime"


def _runtime_source_to_domain(source: str) -> DomainEventSource:
    if source == "replay_runtime":
        return DomainEventSource.REPLAY
    if source in {"paper", "paper_runtime"}:
        return DomainEventSource.PAPER
    if source in {"historical", "historical_runtime"}:
        return DomainEventSource.HISTORICAL
    return DomainEventSource.LIVE


def _event_payload(event: BaseEvent) -> dict[str, Any]:
    data = event.model_dump()
    protocol_fields = {
        "event_id",
        "trace_id",
        "parent_event_id",
        "schema_version",
        "event_type",
        "category",
        "source",
        "symbol",
        "event_time_ms",
        "ingest_time_ms",
        "process_time_ms",
        "clock_mode",
        "metadata",
    }
    payload = {key: value for key, value in data.items() if key not in protocol_fields}
    if event.metadata:
        payload["metadata"] = dict(event.metadata)
    return payload


def to_immutable_event(
    event: BaseEvent,
    *,
    available_time_ms: int | None = None,
    exchange: str | None = None,
) -> ImmutableEvent:
    """Convert transport BaseEvent into the canonical immutable domain event."""

    available = available_time_ms
    if available is None:
        available = int(event.metadata.get("available_time_ms", event.ingest_time_ms))

    processing = max(event.process_time_ms, available)

    return ImmutableEvent(
        event_id=event.event_id,
        event_type=event.event_type,
        symbol=event.symbol or "",
        exchange=exchange or str(event.metadata.get("exchange", DEFAULT_EXCHANGE)),
        event_time_ms=event.event_time_ms,
        available_time_ms=available,
        processing_time_ms=processing,
        payload=FrozenDict(_event_payload(event)),
        source=_runtime_source_to_domain(event.source),
        created_at_ms=event.ingest_time_ms,
    )


def immutable_metadata(event: ImmutableEvent) -> dict[str, Any]:
    return {
        "available_time_ms": event.available_time_ms,
        "processing_time_ms": event.processing_time_ms,
        "exchange": event.exchange,
        "protocol_version": event.protocol_version.value,
        "verification_hash": event.verification_hash,
        "canonical_event_id": event.event_id,
    }


def with_canonical_metadata(
    transport_event: BaseEvent,
    canonical_event: ImmutableEvent,
    extra_metadata: Mapping[str, Any] | None = None,
) -> BaseEvent:
    metadata = dict(transport_event.metadata)
    metadata.update(immutable_metadata(canonical_event))
    if extra_metadata:
        metadata.update(dict(extra_metadata))
    return transport_event.model_copy(update={"metadata": metadata})


def to_transport_event(
    event: ImmutableEvent,
) -> BaseEvent:
    event_cls = get_event_class(event.event_type)
    payload = event.payload.to_dict()
    metadata = dict(payload.pop("metadata", {})) if "metadata" in payload else {}
    metadata.update(immutable_metadata(event))

    return event_cls(
        event_id=event.event_id,
        event_type=event.event_type,
        symbol=event.symbol or None,
        source=_domain_source_to_runtime(event.source),
        event_time_ms=event.event_time_ms,
        ingest_time_ms=event.created_at_ms,
        process_time_ms=event.processing_time_ms,
        metadata=metadata,
        **payload,
    )


def is_canonical_compatible(
    event: Union[ImmutableEvent, BaseEvent],
) -> bool:
    if isinstance(event, ImmutableEvent):
        return bool(event.verification_hash) and event.verify_integrity()
    if isinstance(event, BaseEvent):
        try:
            canonical = to_immutable_event(event)
            return bool(canonical.verification_hash) and canonical.verify_integrity()
        except Exception:
            return False
    return False


__all__ = [
    "to_immutable_event",
    "to_transport_event",
    "is_canonical_compatible",
    "immutable_metadata",
    "with_canonical_metadata",
]
