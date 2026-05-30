from typing import Any

__all__ = ["ContextRunner"]


class ContextRunner:
    def __init__(self, context_builder: Any) -> None:
        self._context_builder = context_builder

    def build(self, symbol: str, timestamp_ms: int) -> Any:
        return self._context_builder.build(symbol, timestamp_ms)

    def update(self, event: Any) -> None:
        self._context_builder.update(event)
