import time
from typing import Optional, Any, Callable
import asyncio

from infrastructure.persistence.cache.redis_client import RedisClient
from infrastructure.utilities.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    CircuitOpenError,
)


class CacheCircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: float = 60.0,
        half_open_max_calls: int = 3,
    ):
        self._breaker = CircuitBreaker(CircuitBreakerConfig(
            name="cache",
            failure_threshold=failure_threshold,
            recovery_timeout=timeout,
            half_open_max_calls=half_open_max_calls,
        ))

    @property
    def state(self) -> CircuitState:
        return self._breaker.state

    async def get(
        self,
        redis_client: RedisClient,
        key: str,
        fallback_func: Optional[Callable] = None,
    ) -> Optional[Any]:
        async def _operation():
            return await redis_client.get(key)

        try:
            return await self._breaker.execute(_operation)
        except CircuitOpenError:
            if fallback_func:
                return await fallback_func(key)
            return None
        except Exception:
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
        async def _operation():
            return await redis_client.set(key, value, ex=ex)

        try:
            return await self._breaker.execute(_operation)
        except CircuitOpenError:
            if fallback_func:
                await fallback_func(key, value)
            return False
        except Exception:
            if fallback_func:
                await fallback_func(key, value)
            return False

    async def get_json(
        self,
        redis_client: RedisClient,
        key: str,
        fallback_func: Optional[Callable] = None,
    ) -> Optional[dict]:
        async def _operation():
            return await redis_client.get_json(key)

        try:
            return await self._breaker.execute(_operation)
        except CircuitOpenError:
            if fallback_func:
                return await fallback_func(key)
            return None
        except Exception:
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
        async def _operation():
            return await redis_client.set_json(key, value, ex=ex)

        try:
            return await self._breaker.execute(_operation)
        except CircuitOpenError:
            if fallback_func:
                await fallback_func(key, value)
            return False
        except Exception:
            if fallback_func:
                await fallback_func(key, value)
            return False

    def reset(self):
        self._breaker.reset()

    def get_stats(self) -> dict:
        return self._breaker.get_stats()


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
