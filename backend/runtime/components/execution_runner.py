from typing import Any, Dict

__all__ = ["ExecutionRunner"]


class ExecutionRunner:
    def __init__(self, adapters: Dict[str, Any]) -> None:
        self._adapters: Dict[str, Any] = dict(adapters)

    def execute(self, signal: Any, mode: str) -> Any:
        adapter = self._adapters.get(mode)
        if adapter is None:
            raise ValueError(f"unknown execution mode: {mode}")
        return adapter.execute(signal)

    def register_adapter(self, mode: str, adapter: Any) -> None:
        self._adapters[mode] = adapter
