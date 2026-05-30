from __future__ import annotations

from types import MappingProxyType
from typing import Mapping


STATE_OWNERS: Mapping[str, str] = MappingProxyType(
    {
        "market_stream_ordering": "ingestion_runtime",
        "market_buffer": "ingestion_runtime",
        "raw_event_buffer": "ingestion_runtime",
        "feature_materialization": "feature_runtime",
        "feature_availability": "feature_runtime",
        "feature_cache": "feature_runtime",
        "feature_pit_index": "feature_runtime",
        "signal_sequence": "signal_runtime",
        "signal_cooldown": "signal_runtime",
        "signal_debounce": "signal_runtime",
        "pending_orders": "execution_runtime",
        "fill_lifecycle": "execution_runtime",
        "order_state": "execution_runtime",
        "execution_reconciliation": "execution_runtime",
        "positions": "portfolio_runtime",
        "pnl_timeline": "portfolio_runtime",
        "exposure": "portfolio_runtime",
        "capital_allocation": "portfolio_runtime",
        "replay_cursor": "replay_runtime",
        "replay_session": "replay_runtime",
        "replay_deterministic_state": "replay_runtime",
        "projection_read_model": "projection_runtime",
        "projection_cache": "projection_runtime",
        "correlation_matrix": "correlation_runtime",
        "correlation_state": "correlation_runtime",
        "regime_state": "regime_runtime",
        "regime_classification": "regime_runtime",
        "narrative_state": "narrative_runtime",
        "narrative_cache": "narrative_runtime",
        "kernel_state": "kernel_runtime",
        "kernel_trajectory": "kernel_runtime",
        "kernel_event_log": "kernel_runtime",
        "checkpoint_state": "kernel_runtime",
        "checkpoint_index": "kernel_runtime",
        "snapshot_state": "kernel_runtime",
        "recovery_state": "kernel_runtime",
    }
)


class OwnershipViolation(RuntimeError):
    pass


def get_state_owner(state_name: str) -> str:
    try:
        return STATE_OWNERS[state_name]
    except KeyError as exc:
        known = ", ".join(sorted(STATE_OWNERS))
        raise KeyError(f"Unknown state owner '{state_name}'. Known states: {known}") from exc


def owns_state(runtime_name: str, state_name: str) -> bool:
    return STATE_OWNERS.get(state_name) == runtime_name


def assert_state_owner(runtime_name: str, state_name: str) -> None:
    expected = get_state_owner(state_name)
    if runtime_name != expected:
        raise OwnershipViolation(
            f"State '{state_name}' is owned by '{expected}', not '{runtime_name}'"
        )


def assert_known_state(state_name: str) -> None:
    get_state_owner(state_name)


__all__ = [
    "OwnershipViolation",
    "STATE_OWNERS",
    "assert_known_state",
    "assert_state_owner",
    "get_state_owner",
    "owns_state",
]
