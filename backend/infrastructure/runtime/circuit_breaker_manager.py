"""
Circuit Breaker Manager - 熔断器管理器

管理多个熔断器实例，用于不同服务:
- ai_runtime: AI/LLM 服务
- exchange_api: 交易所 API
- websocket_push: WebSocket 推送
- database: 数据库操作
- cache: 缓存操作

特性:
- 统一管理多个熔断器
- 自动恢复机制
- 降级回退处理
"""

import asyncio
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Callable, Awaitable
from datetime import datetime
import time

from infrastructure.logging import get_logger

logger = get_logger("runtime_governor.circuit_breaker")


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    name: str = "default"
    failure_threshold: int = 5
    recovery_timeout_ms: int = 30000
    half_open_max_calls: int = 3
    success_threshold: int = 2
    expected_exceptions: tuple = (Exception,)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout_ms": self.recovery_timeout_ms,
            "half_open_max_calls": self.half_open_max_calls,
            "success_threshold": self.success_threshold,
        }


class CircuitBreakerOpenError(Exception):
    def __init__(self, name: str, message: str = ""):
        self.name = name
        super().__init__(f"Circuit '{name}' is open. {message}")


@dataclass
class CircuitStats:
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[float] = None
    half_open_calls: int = 0
    total_calls: int = 0
    total_failures: int = 0
    total_successes: int = 0
    total_rejections: int = 0


class CircuitBreaker:
    def __init__(
        self,
        config: CircuitBreakerConfig,
        fallback: Optional[Callable[..., Awaitable[Any]]] = None,
    ):
        self.config = config
        self._fallback = fallback
        self._stats = CircuitStats()
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        if self._stats.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._stats.state = CircuitState.HALF_OPEN
                self._stats.half_open_calls = 0
        return self._stats.state

    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN

    @property
    def is_closed(self) -> bool:
        return self.state == CircuitState.CLOSED

    def _should_attempt_reset(self) -> bool:
        if self._stats.last_failure_time is None:
            return True
        elapsed_ms = (time.time() - self._stats.last_failure_time) * 1000
        return elapsed_ms >= self.config.recovery_timeout_ms

    async def call(
        self,
        func: Callable[..., Awaitable[Any]],
        *args,
        **kwargs,
    ) -> Any:
        async with self._lock:
            current_state = self.state
            self._stats.total_calls += 1

            if current_state == CircuitState.OPEN:
                self._stats.total_rejections += 1
                logger.warning(
                    f"Circuit '{self.config.name}' is OPEN, rejecting request"
                )
                if self._fallback:
                    return await self._fallback(*args, **kwargs)
                raise CircuitBreakerOpenError(self.config.name)

            if current_state == CircuitState.HALF_OPEN:
                if self._stats.half_open_calls >= self.config.half_open_max_calls:
                    self._stats.total_rejections += 1
                    logger.warning(
                        f"Circuit '{self.config.name}' half-open limit reached"
                    )
                    if self._fallback:
                        return await self._fallback(*args, **kwargs)
                    raise CircuitBreakerOpenError(
                        self.config.name, "half-open limit reached"
                    )
                self._stats.half_open_calls += 1

        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except self.config.expected_exceptions as e:
            await self._on_failure()
            raise

    async def _on_success(self) -> None:
        async with self._lock:
            self._stats.total_successes += 1

            if self._stats.state == CircuitState.HALF_OPEN:
                self._stats.success_count += 1
                if self._stats.success_count >= self.config.success_threshold:
                    logger.info(
                        f"Circuit '{self.config.name}' transitioning from "
                        f"HALF_OPEN to CLOSED"
                    )
                    self._stats.state = CircuitState.CLOSED
                    self._stats.failure_count = 0
                    self._stats.success_count = 0
                    self._stats.half_open_calls = 0
            else:
                self._stats.failure_count = 0

    async def _on_failure(self) -> None:
        async with self._lock:
            self._stats.last_failure_time = time.time()
            self._stats.total_failures += 1

            if self._stats.state == CircuitState.HALF_OPEN:
                logger.warning(
                    f"Circuit '{self.config.name}' failed in HALF_OPEN, "
                    f"transitioning to OPEN"
                )
                self._stats.state = CircuitState.OPEN
                self._stats.success_count = 0
                self._stats.half_open_calls = 0
            else:
                self._stats.failure_count += 1
                if self._stats.failure_count >= self.config.failure_threshold:
                    logger.warning(
                        f"Circuit '{self.config.name}' failure threshold reached, "
                        f"transitioning to OPEN"
                    )
                    self._stats.state = CircuitState.OPEN

    def get_stats(self) -> Dict[str, Any]:
        return {
            "name": self.config.name,
            "state": self.state.value,
            "failure_count": self._stats.failure_count,
            "success_count": self._stats.success_count,
            "last_failure_time": self._stats.last_failure_time,
            "half_open_calls": self._stats.half_open_calls,
            "total_calls": self._stats.total_calls,
            "total_failures": self._stats.total_failures,
            "total_successes": self._stats.total_successes,
            "total_rejections": self._stats.total_rejections,
        }

    def reset(self) -> None:
        self._stats = CircuitStats()
        logger.info(f"Circuit '{self.config.name}' reset to CLOSED")

    def force_open(self) -> None:
        self._stats.state = CircuitState.OPEN
        self._stats.last_failure_time = time.time()
        logger.warning(f"Circuit '{self.config.name}' forced to OPEN")

    def force_close(self) -> None:
        self._stats.state = CircuitState.CLOSED
        self._stats.failure_count = 0
        self._stats.success_count = 0
        self._stats.half_open_calls = 0
        logger.info(f"Circuit '{self.config.name}' forced to CLOSED")


DEFAULT_CIRCUIT_CONFIGS = {
    "ai_runtime": CircuitBreakerConfig(
        name="ai_runtime",
        failure_threshold=3,
        recovery_timeout_ms=60000,
        half_open_max_calls=2,
        success_threshold=2,
    ),
    "exchange_api": CircuitBreakerConfig(
        name="exchange_api",
        failure_threshold=3,
        recovery_timeout_ms=10000,
        half_open_max_calls=3,
        success_threshold=2,
    ),
    "websocket_push": CircuitBreakerConfig(
        name="websocket_push",
        failure_threshold=10,
        recovery_timeout_ms=5000,
        half_open_max_calls=5,
        success_threshold=3,
    ),
    "database": CircuitBreakerConfig(
        name="database",
        failure_threshold=5,
        recovery_timeout_ms=30000,
        half_open_max_calls=3,
        success_threshold=2,
    ),
    "cache": CircuitBreakerConfig(
        name="cache",
        failure_threshold=5,
        recovery_timeout_ms=10000,
        half_open_max_calls=5,
        success_threshold=2,
    ),
    "kafka": CircuitBreakerConfig(
        name="kafka",
        failure_threshold=5,
        recovery_timeout_ms=15000,
        half_open_max_calls=3,
        success_threshold=2,
    ),
    "redis": CircuitBreakerConfig(
        name="redis",
        failure_threshold=5,
        recovery_timeout_ms=10000,
        half_open_max_calls=5,
        success_threshold=2,
    ),
}

DEFAULT_FALLBACKS = {
    "ai_runtime": lambda *a, **k: {
        "status": "ai_unavailable",
        "message": "AI temporarily unavailable",
        "fallback": True,
    },
    "exchange_api": lambda *a, **k: {
        "status": "exchange_unavailable",
        "message": "Exchange API temporarily unavailable",
        "fallback": True,
    },
    "websocket_push": lambda *a, **k: None,
    "database": lambda *a, **k: None,
    "cache": lambda *a, **k: None,
}


class CircuitBreakerManager:
    def __init__(self):
        self._circuits: Dict[str, CircuitBreaker] = {}
        self._initialize_default_circuits()

    def _initialize_default_circuits(self) -> None:
        for name, config in DEFAULT_CIRCUIT_CONFIGS.items():
            fallback = DEFAULT_FALLBACKS.get(name)
            self._circuits[name] = CircuitBreaker(config, fallback)

    def get(self, name: str) -> CircuitBreaker:
        if name not in self._circuits:
            config = CircuitBreakerConfig(name=name)
            self._circuits[name] = CircuitBreaker(config)
        return self._circuits[name]

    def register(
        self,
        name: str,
        config: CircuitBreakerConfig,
        fallback: Optional[Callable[..., Awaitable[Any]]] = None,
    ) -> CircuitBreaker:
        circuit = CircuitBreaker(config, fallback)
        self._circuits[name] = circuit
        return circuit

    async def call(
        self,
        circuit_name: str,
        func: Callable[..., Awaitable[Any]],
        *args,
        **kwargs,
    ) -> Any:
        circuit = self.get(circuit_name)
        return await circuit.call(func, *args, **kwargs)

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        return {name: circuit.get_stats() for name, circuit in self._circuits.items()}

    def get_open_circuits(self) -> list[str]:
        return [name for name, circuit in self._circuits.items() if circuit.is_open]

    def get_healthy_circuits(self) -> list[str]:
        return [name for name, circuit in self._circuits.items() if circuit.is_closed]

    def reset_all(self) -> None:
        for circuit in self._circuits.values():
            circuit.reset()

    def reset(self, name: str) -> None:
        if name in self._circuits:
            self._circuits[name].reset()

    def force_open(self, name: str) -> None:
        if name in self._circuits:
            self._circuits[name].force_open()

    def force_close(self, name: str) -> None:
        if name in self._circuits:
            self._circuits[name].force_close()

    def is_healthy(self) -> bool:
        critical_circuits = ["exchange_api", "database"]
        for name in critical_circuits:
            if name in self._circuits and self._circuits[name].is_open:
                return False
        return True


_circuit_breaker_manager: Optional[CircuitBreakerManager] = None


def get_circuit_breaker_manager() -> CircuitBreakerManager:
    global _circuit_breaker_manager
    if _circuit_breaker_manager is None:
        _circuit_breaker_manager = CircuitBreakerManager()
    return _circuit_breaker_manager
