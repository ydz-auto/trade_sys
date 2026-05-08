"""
缓存熔断器
防止缓存失效影响主业务
"""

import time
from typing import Optional, Any, Callable
from enum import Enum
import asyncio

from infrastructure.cache.redis_client import RedisClient


class CircuitBreakerState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CacheCircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: float = 60.0,
        half_open_max_calls: int = 3,
    ):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.half_open_max_calls = half_open_max_calls

        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._state = CircuitBreakerState.CLOSED

        self._half_open_calls = 0

    @property
    def state(self) -> CircuitBreakerState:
        if self._state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self._state = CircuitBreakerState.HALF_OPEN
                self._half_open_calls = 0
        return self._state

    def _should_attempt_reset(self) -> bool:
        if self._last_failure_time is None:
            return True
        return (time.time() - self._last_failure_time) >= self.timeout

    def _record_success(self):
        self._failure_count = 0
        self._state = CircuitBreakerState.CLOSED
        self._half_open_calls = 0

    def _record_failure(self):
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._failure_count >= self.failure_threshold:
            self._state = CircuitBreakerState.OPEN

    async def get(
        self,
        redis_client: RedisClient,
        key: str,
        fallback_func: Optional[Callable] = None,
    ) -> Optional[Any]:
        if self.state == CircuitBreakerState.OPEN:
            if fallback_func:
                return await fallback_func(key)
            return None

        try:
            if self.state == CircuitBreakerState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    return None
                self._half_open_calls += 1

            value = await redis_client.get(key)
            self._record_success()
            return value

        except Exception as e:
            self._record_failure()
            if fallback_func:
                return await fallback_func(key)
            return None

    async def set(
        self,
        redis_client: RedisClient,
        key: str,
        value: Any,
        ex: Optional[int] = None,
        fallback_func: Optional[Callable] = None,
    ) -> bool:
        if self.state == CircuitBreakerState.OPEN:
            if fallback_func:
                await fallback_func(key, value)
            return False

        try:
            if self.state == CircuitBreakerState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    return False
                self._half_open_calls += 1

            result = await redis_client.set(key, value, ex=ex)
            self._record_success()
            return result

        except Exception as e:
            self._record_failure()
            if fallback_func:
                await fallback_func(key, value)
            return False

    async def get_json(
        self,
        redis_client: RedisClient,
        key: str,
        fallback_func: Optional[Callable] = None,
    ) -> Optional[dict]:
        if self.state == CircuitBreakerState.OPEN:
            if fallback_func:
                return await fallback_func(key)
            return None

        try:
            if self.state == CircuitBreakerState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    return None
                self._half_open_calls += 1

            value = await redis_client.get_json(key)
            self._record_success()
            return value

        except Exception as e:
            self._record_failure()
            if fallback_func:
                return await fallback_func(key)
            return None

    async def set_json(
        self,
        redis_client: RedisClient,
        key: str,
        value: dict,
        ex: Optional[int] = None,
        fallback_func: Optional[Callable] = None,
    ) -> bool:
        if self.state == CircuitBreakerState.OPEN:
            if fallback_func:
                await fallback_func(key, value)
            return False

        try:
            if self.state == CircuitBreakerState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    return False
                self._half_open_calls += 1

            result = await redis_client.set_json(key, value, ex=ex)
            self._record_success()
            return result

        except Exception as e:
            self._record_failure()
            if fallback_func:
                await fallback_func(key, value)
            return False

    def reset(self):
        self._failure_count = 0
        self._last_failure_time = None
        self._state = CircuitBreakerState.CLOSED
        self._half_open_calls = 0

    def get_stats(self) -> dict:
        return {
            "state": self.state.value,
            "failure_count": self._failure_count,
            "last_failure_time": self._last_failure_time,
            "half_open_calls": self._half_open_calls,
        }


class RateLimiter:
    def __init__(self, redis_client: RedisClient):
        self.redis = redis_client

    async def is_allowed(
        self,
        user_id: str,
        limit: int = 100,
        window: int = 60,
    ) -> tuple[bool, int]:
        key = f"user:rate:{user_id}"

        current = await self.redis.incr(key)

        if current == 1:
            await self.redis.expire(key, window)

        return current <= limit, limit - current if current <= limit else 0

    async def consume(
        self,
        user_id: str,
        amount: int = 1,
        limit: int = 100,
        window: int = 60,
    ) -> tuple[bool, int]:
        key = f"user:rate:{user_id}"

        current = await self.redis.incr(key)

        if current == 1:
            await self.redis.expire(key, window)

        allowed = current <= limit
        remaining = max(0, limit - current)

        return allowed, remaining


class DistributedLock:
    def __init__(self, redis_client: RedisClient):
        self.redis = redis_client
        self._locks: dict = {}

    async def acquire(
        self,
        lock_name: str,
        timeout: int = 30,
        blocking: bool = True,
        blocking_timeout: float = 10.0,
    ) -> bool:
        key = f"lock:{lock_name}"
        lock_value = f"{time.time()}:{id(self)}"

        start_time = time.time()

        while True:
            acquired = await self.redis.client.set(
                key, lock_value, nx=True, ex=timeout
            )
            if acquired:
                self._locks[lock_name] = lock_value
                return True

            if not blocking:
                return False

            if (time.time() - start_time) >= blocking_timeout:
                return False

            await asyncio.sleep(0.1)

    async def release(self, lock_name: str) -> bool:
        key = f"lock:{lock_name}"
        lock_value = self._locks.get(lock_name)

        if not lock_value:
            return False

        current_value = await self.redis.get(key)
        if current_value == lock_value:
            await self.redis.delete(key)
            del self._locks[lock_name]
            return True

        return False

    async def extend(self, lock_name: str, timeout: int = 30) -> bool:
        key = f"lock:{lock_name}"
        lock_value = self._locks.get(lock_name)

        if not lock_value:
            return False

        current_value = await self.redis.get(key)
        if current_value == lock_value:
            await self.redis.expire(key, timeout)
            return True

        return False
