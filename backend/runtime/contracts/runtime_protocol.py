from __future__ import annotations

from typing import Any, Mapping, Protocol, runtime_checkable, Union

from runtime.kernel.state.runtime_state import RuntimeState


RuntimeSnapshot = Mapping[str, Any]
RuntimeHealth = Mapping[str, Any]
RecoveryPoint = Union[Mapping[str, Any], str, None]


@runtime_checkable
class RuntimeProtocol(Protocol):
    """Stable runtime contract for orchestration, replay, and recovery.

    Existing runtimes can implement this directly or expose a small adapter.
    The contract is intentionally smaller than BaseRuntime so stateful and
    analytical runtimes share the same control surface.
    """

    @property
    def name(self) -> str:
        ...

    @property
    def state(self) -> RuntimeState:
        ...

    async def start(self) -> None:
        ...

    async def stop(self) -> None:
        ...

    async def on_event(self, event: Any) -> None:
        ...

    async def get_state(self) -> Mapping[str, Any]:
        ...

    async def snapshot(self) -> RuntimeSnapshot:
        ...

    async def recover(self, checkpoint: RecoveryPoint = None) -> None:
        ...

    async def health(self) -> RuntimeHealth:
        ...


__all__ = [
    "RecoveryPoint",
    "RuntimeHealth",
    "RuntimeProtocol",
    "RuntimeSnapshot",
]
