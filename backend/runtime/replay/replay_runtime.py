import asyncio
import logging
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional

from runtime.kernel.runtime_container import RuntimeContainer, RuntimeConfig
from runtime.kernel.runtime_context import RuntimeContext
from runtime.kernel.runtime_context import RuntimeState
from runtime.components.context_runner import ContextRunner
from runtime.components.strategy_runner import StrategyRunner


__all__ = [
    "ReplaySessionState",
    "ReplaySession",
    "ReplayRuntime",
]


class ReplaySessionState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class ReplaySession:
    session_id: str
    symbol: str
    start_ts: int
    end_ts: int
    capital: float
    state: ReplaySessionState = ReplaySessionState.IDLE
    current_ts: int = 0
    last_processed_ts: int = 0


class ReplayRuntime(RuntimeContainer):

    def __init__(
        self,
        config: Optional[RuntimeConfig] = None,
        context_runner: ContextRunner = None,
        strategy_runner: StrategyRunner = None,
        execution_engine: Any = None,
        logger: Optional[logging.Logger] = None,
        now_ms: Optional[Callable[[], int]] = None,
    ) -> None:
        super().__init__(config=config, logger=logger, now_ms=now_ms)
        self.context_runner = context_runner
        self.strategy_runner = strategy_runner
        self.execution_engine = execution_engine
        self._session: Optional[ReplaySession] = None
        self._event_queue: asyncio.Queue = asyncio.Queue()

    async def initialize(self) -> None:
        self.logger.info("ReplayRuntime initialized")

    async def run(self) -> None:
        if self._session is None:
            self.logger.warning("No active replay session")
            return
        while self._session.state == ReplaySessionState.RUNNING:
            event = await self._event_queue.get()
            await self._process_event(event)

    async def shutdown(self) -> None:
        if self._session is not None and self._session.state in (
            ReplaySessionState.RUNNING,
            ReplaySessionState.PAUSED,
        ):
            self._session.state = ReplaySessionState.COMPLETED
        self.logger.info("ReplayRuntime shutdown")

    def start_session(self, symbol: str, start: int, end: int, capital: float) -> str:
        session_id = uuid.uuid4().hex
        self._session = ReplaySession(
            session_id=session_id,
            symbol=symbol,
            start_ts=start,
            end_ts=end,
            capital=capital,
        )
        return session_id

    def stop_session(self) -> None:
        if self._session is not None:
            self._session.state = ReplaySessionState.COMPLETED

    def pause(self) -> None:
        if self._session is not None:
            self._session.state = ReplaySessionState.PAUSED

    def resume(self) -> None:
        if self._session is not None:
            self._session.state = ReplaySessionState.RUNNING

    async def step(self) -> None:
        if self._event_queue.empty():
            return
        event = self._event_queue.get_nowait()
        await self._process_event(event)

    async def _process_event(self, event: Any) -> None:
        if self._session is None:
            return
        event_ts = getattr(event, "ts", 0)
        if not self._check_time_causality(event_ts, self._session.last_processed_ts):
            return
        self._session.current_ts = event_ts
        self.context_runner.update(event)
        ctx = self.context_runner.build()
        signal = self.strategy_runner.run()
        if signal is not None:
            self.execution_engine.execute(signal)
        self._session.last_processed_ts = event_ts

    @staticmethod
    def _check_time_causality(current_ts: int, last_ts: int) -> bool:
        return current_ts >= last_ts
