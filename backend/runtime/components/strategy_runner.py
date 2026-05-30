from typing import Any, Optional

__all__ = ["StrategyRunner"]


class StrategyRunner:
    def __init__(self) -> None:
        pass

    def run(self, ctx: Any, strategy: Any) -> Optional[Any]:
        signal = strategy.generate_signal(ctx)
        if signal is None:
            return None
        return signal
