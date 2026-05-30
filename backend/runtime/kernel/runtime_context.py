import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from runtime.kernel.runtime_config import RuntimeConfig


class RuntimeState(str, Enum):
    CREATED = "created"
    REGISTERED = "registered"
    INITIALIZING = "initializing"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    DEGRADED = "degraded"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    FAILED = "failed"
    RECOVERING = "recovering"


class RuntimeType(str, Enum):
    LIVE = "live"
    BACKTEST = "backtest"
    REPLAY = "replay"


def _default_now_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class RuntimeContext:
    config: RuntimeConfig
    state: RuntimeState = RuntimeState.CREATED
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    stats: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    _shutdown_event: asyncio.Event = field(default_factory=asyncio.Event)
    _now_ms: Callable[[], int] = field(default_factory=lambda: _default_now_ms)

    def record_stat(self, key: str, value: Any) -> None:
        self.stats[key] = value

    def increment_stat(self, key: str, delta: int = 1) -> None:
        self.stats[key] = self.stats.get(key, 0) + delta

    def record_error(self, error: str) -> None:
        self.errors.append(error)

    @property
    def uptime_seconds(self) -> float:
        if self.start_time is None:
            return 0.0
        end = self.end_time or datetime.fromtimestamp(self._now_ms() / 1000)
        return (end - self.start_time).total_seconds()

    def request_shutdown(self) -> None:
        self._shutdown_event.set()

    def is_shutdown_requested(self) -> bool:
        return self._shutdown_event.is_set()

    async def wait_for_shutdown(self, timeout: float = None) -> bool:
        try:
            await asyncio.wait_for(
                self._shutdown_event.wait(),
                timeout=timeout,
            )
            return True
        except asyncio.TimeoutError:
            return False


__all__ = ["RuntimeContext", "RuntimeState", "RuntimeType"]
