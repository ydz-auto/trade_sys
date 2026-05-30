import asyncio
import logging
import signal
import traceback
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Callable, Dict, List, Mapping, Optional, Union

from runtime.kernel.runtime_config import RuntimeConfig
from runtime.kernel.runtime_context import RuntimeContext, _default_now_ms
from runtime.kernel.runtime_context import RuntimeState


RuntimeSnapshot = Mapping[str, Any]
RuntimeHealth = Mapping[str, Any]
RecoveryPoint = Union[Mapping[str, Any], str, None]


class RuntimeContainer(ABC):

    def __init__(
        self,
        config: Optional[RuntimeConfig] = None,
        logger: Optional[logging.Logger] = None,
        now_ms: Optional[Callable[[], int]] = None,
    ):
        self.config = config or RuntimeConfig.from_env()
        self.context = RuntimeContext(config=self.config, _now_ms=now_ms or _default_now_ms)
        self.logger = logger or self._create_default_logger()
        self._tasks: List[asyncio.Task] = []
        self._shutdown_handlers: List[Callable] = []

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def state(self) -> RuntimeState:
        return self.context.state

    @abstractmethod
    async def initialize(self) -> None:
        pass

    @abstractmethod
    async def run(self) -> None:
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        pass

    async def health_check(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state.value,
            "uptime": self.context.uptime_seconds,
            "stats": self.context.stats,
            "errors_count": len(self.context.errors),
            "healthy": self.state == RuntimeState.RUNNING,
        }

    async def on_event(self, event: Any) -> None:
        raise NotImplementedError(f"{self.name} does not implement on_event()")

    async def get_state(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state.value,
            "stats": dict(self.context.stats),
        }

    async def snapshot(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state.value,
            "stats": dict(self.context.stats),
            "errors": list(self.context.errors),
        }

    async def recover(self, checkpoint: Any = None) -> None:
        if checkpoint is not None:
            self.logger.info(f"Recover called with checkpoint: {checkpoint}")

    async def health(self) -> Dict[str, Any]:
        return await self.health_check()

    def on_shutdown(self, handler: Callable) -> None:
        self._shutdown_handlers.append(handler)

    async def start(self) -> None:
        try:
            await self._set_state(RuntimeState.INITIALIZING)
            self.context.start_time = datetime.fromtimestamp(self.context._now_ms() / 1000)

            await self._setup_signal_handlers()
            await self.initialize()

            await self._set_state(RuntimeState.RUNNING)
            self.logger.info(f"Runtime {self.name} started")

            await self.run()

        except Exception as e:
            self.logger.error(f"Runtime error: {e}")
            self.logger.error(f"Traceback:\n{traceback.format_exc()}")
            self.context.record_error(str(e))
            await self._set_state(RuntimeState.ERROR)
            raise

        finally:
            await self._set_state(RuntimeState.STOPPING)
            await self._run_shutdown_handlers()
            await self.shutdown()
            self.context.end_time = datetime.fromtimestamp(self.context._now_ms() / 1000)
            await self._set_state(RuntimeState.STOPPED)
            self.logger.info(f"Runtime {self.name} stopped. Uptime: {self.context.uptime_seconds:.1f}s")

    async def stop(self) -> None:
        self.context.request_shutdown()

    async def run_forever(self) -> None:
        await self.context.wait_for_shutdown()

    def create_task(self, coro, name=None) -> asyncio.Task:
        task = asyncio.create_task(coro)
        if name:
            task.set_name(name)
        self._tasks.append(task)
        return task

    async def wait_for_tasks(self, timeout=None) -> None:
        if not self._tasks:
            return

        try:
            await asyncio.wait_for(
                asyncio.gather(*self._tasks, return_exceptions=True),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            self.logger.warning(f"Tasks did not complete within {timeout}s")
            for task in self._tasks:
                if not task.done():
                    task.cancel()

    def _create_default_logger(self) -> logging.Logger:
        log = logging.getLogger(self.config.name)
        log.setLevel(getattr(logging, self.config.log_level, logging.INFO))
        if not log.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            ))
            log.addHandler(handler)
        return log

    async def _set_state(self, state: RuntimeState) -> None:
        self.context.state = state
        self.logger.info(f"Runtime state changed: {state.value}")

    async def _setup_signal_handlers(self) -> None:
        import sys
        if sys.platform == "win32":
            self.logger.info("Windows platform detected, skipping signal handlers")
            return

        loop = asyncio.get_running_loop()

        def handle_signal(sig):
            self.logger.info(f"Received signal {sig}, requesting shutdown...")
            self.context.request_shutdown()

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda s=sig: handle_signal(s))

    async def _run_shutdown_handlers(self) -> None:
        for handler in self._shutdown_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler()
                else:
                    handler()
            except Exception as e:
                self.logger.error(f"Shutdown handler error: {e}")


__all__ = [
    "RecoveryPoint",
    "RuntimeContainer",
    "RuntimeHealth",
    "RuntimeSnapshot",
]
