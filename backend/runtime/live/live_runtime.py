import asyncio
import logging
from enum import Enum
from typing import Any, Callable, Optional

from runtime.kernel.runtime_container import RuntimeContainer, RuntimeConfig
from runtime.kernel.runtime_context import RuntimeContext
from runtime.kernel.runtime_context import RuntimeState
from runtime.components.context_runner import ContextRunner
from runtime.components.strategy_runner import StrategyRunner
from runtime.components.execution_runner import ExecutionRunner
from runtime.components.ingestion_runner import IngestionRunner


__all__ = [
    "TradingMode",
    "LiveRuntime",
]


class TradingMode(str, Enum):
    PAPER = "paper"
    LIVE = "live"


class LiveRuntime(RuntimeContainer):

    def __init__(
        self,
        config: Optional[RuntimeConfig] = None,
        ingestion_runner: IngestionRunner = None,
        context_runner: ContextRunner = None,
        strategy_runner: StrategyRunner = None,
        execution_runner: ExecutionRunner = None,
        strategy: Any = None,
        trading_mode: TradingMode = TradingMode.PAPER,
        logger: Optional[logging.Logger] = None,
        now_ms: Optional[Callable[[], int]] = None,
    ) -> None:
        super().__init__(config=config, logger=logger, now_ms=now_ms)
        self._ingestion_runner = ingestion_runner
        self._context_runner = context_runner
        self._strategy_runner = strategy_runner
        self._execution_runner = execution_runner
        self._strategy = strategy
        self._trading_mode = trading_mode

    async def initialize(self) -> None:
        self.logger.info(f"LiveRuntime initialized with trading_mode={self._trading_mode.value}")

    async def run(self) -> None:
        while not self.context.is_shutdown_requested():
            events = self._ingestion_runner.collect()
            for event in events:
                self._context_runner.update(event)
                symbol = getattr(event, "symbol", "")
                timestamp_ms = getattr(event, "timestamp_ms", 0)
                ctx = self._context_runner.build(symbol, timestamp_ms)
                signal = self._strategy_runner.run(ctx, self._strategy)
                if signal is not None:
                    self._execution_runner.execute(signal, self._trading_mode)
            self.context.increment_stat("events_processed")
            await asyncio.sleep(0.001)

    async def shutdown(self) -> None:
        self.logger.info("LiveRuntime shutdown")
        self.context.increment_stat("shutdown_count")

    def set_trading_mode(self, mode: TradingMode) -> None:
        self._trading_mode = mode
