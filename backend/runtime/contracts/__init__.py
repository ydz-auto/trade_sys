"""Stable runtime contract public API."""

from runtime.contracts.canonical_event import (
    CanonicalEvent,
    compute_state_hash,
    validate_canonical_event,
)
from runtime.contracts.event_adapter import (
    immutable_metadata,
    is_canonical_compatible,
    to_immutable_event,
    to_transport_event,
    with_canonical_metadata,
)
from runtime.contracts.event_factory import create_live_event, create_replay_event
from runtime.contracts.runtime_protocol import (
    RecoveryPoint,
    RuntimeHealth,
    RuntimeProtocol,
    RuntimeSnapshot,
)

__all__ = [
    "CanonicalEvent",
    "RecoveryPoint",
    "RuntimeHealth",
    "RuntimeProtocol",
    "RuntimeSnapshot",
    "compute_state_hash",
    "create_live_event",
    "create_replay_event",
    "immutable_metadata",
    "is_canonical_compatible",
    "to_immutable_event",
    "to_transport_event",
    "validate_canonical_event",
    "with_canonical_metadata",
]
