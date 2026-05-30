from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Tuple

from domain.event.protocol import ImmutableEvent, EventProtocolVersion


CanonicalEvent = ImmutableEvent


def validate_canonical_event(event: CanonicalEvent) -> Tuple[bool, List[str]]:
    issues: List[str] = []

    if not event.event_id:
        issues.append("event_id is empty")
    if not event.event_type:
        issues.append("event_type is empty")
    if not event.verification_hash:
        issues.append("verification_hash is empty")
    elif not event.verify_integrity():
        issues.append("verification_hash mismatch")

    if event.event_time_ms <= 0:
        issues.append("event_time_ms must be positive")
    if event.available_time_ms <= 0:
        issues.append("available_time_ms must be positive")
    if event.processing_time_ms <= 0:
        issues.append("processing_time_ms must be positive")

    if event.event_time_ms > event.available_time_ms:
        issues.append("event_time_ms > available_time_ms")
    if event.available_time_ms > event.processing_time_ms:
        issues.append("available_time_ms > processing_time_ms")

    if event.protocol_version not in (EventProtocolVersion.V1, EventProtocolVersion.V2):
        issues.append(f"unsupported protocol_version: {event.protocol_version}")

    return len(issues) == 0, issues


def compute_state_hash(events: List[CanonicalEvent]) -> str:
    hashes = [e.verification_hash for e in events if e.verification_hash]
    content = json.dumps(hashes, sort_keys=True).encode("utf-8")
    return hashlib.sha256(content).hexdigest()[:32]


__all__ = [
    "CanonicalEvent",
    "validate_canonical_event",
    "compute_state_hash",
]
