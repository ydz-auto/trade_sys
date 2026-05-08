"""
缓存管理器
支持多种缓存策略
"""

import asyncio
from typing import Optional, Dict, List, Any, Callable
from datetime import datetime
import json

from infrastructure.cache.redis_client import RedisClient, get_redis_client
from infrastructure.cache.config import (
    CACHE_TTL,
    DEFAULT_TTL,
    CacheStrategy,
    CACHE_KEY_PREFIX,
)
from infrastructure.cache.keys import CacheKey, KeyPattern


class CacheManager:
    def __init__(self, redis_client: Optional[RedisClient] = None):
        self.redis = redis_client or get_redis_client()
        self._memory_cache: Dict[str, Any] = {}
        self._default_ttl = DEFAULT_TTL

    def set_default_ttl(self, ttl: int):
        self._default_ttl = ttl

    async def get(
        self,
        key: str,
        default: Any = None,
        use_memory: bool = True,
    ) -> Any:
        if use_memory and key in self._memory_cache:
            return self._memory_cache[key]

        value = await self.redis.get(key)
        if value is None:
            return default

        try:
            result = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            result = value

        if use_memory:
            self._memory_cache[key] = result

        return result

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        use_memory: bool = True,
    ) -> bool:
        if use_memory:
            self._memory_cache[key] = value

        ttl = ttl or self._default_ttl

        if isinstance(value, (dict, list)):
            return await self.redis.set_json(key, value, ex=ttl)
        else:
            return await self.redis.set(key, value, ex=ttl)

    async def delete(self, key: str, use_memory: bool = True) -> int:
        if use_memory and key in self._memory_cache:
            del self._memory_cache[key]

        return await self.redis.delete(key)

    async def delete_pattern(self, pattern: str) -> int:
        return await self.redis.delete_pattern(pattern)

    async def exists(self, key: str) -> bool:
        return await self.redis.exists(key)

    async def write_through(
        self,
        key: str,
        value: Any,
        db_write_func: Callable,
        ttl: Optional[int] = None,
        **db_kwargs,
    ) -> Any:
        await db_write_func(value, **db_kwargs)

        ttl = ttl or self._default_ttl
        if isinstance(value, (dict, list)):
            await self.redis.set_json(key, value, ex=ttl)
        else:
            await self.redis.set(key, value, ex=ttl)

        return value

    async def write_behind(
        self,
        key: str,
        value: Any,
        db_write_func: Callable,
        ttl: Optional[int] = None,
        **db_kwargs,
    ) -> Any:
        ttl = ttl or self._default_ttl
        if isinstance(value, (dict, list)):
            await self.redis.set_json(key, value, ex=ttl)
        else:
            await self.redis.set(key, value, ex=ttl)

        asyncio.create_task(db_write_func(value, **db_kwargs))

        return value

    async def read_aside(
        self,
        key: str,
        db_read_func: Callable,
        ttl: Optional[int] = None,
        use_memory: bool = True,
        **db_kwargs,
    ) -> Any:
        value = await self.get(key, use_memory=use_memory)
        if value is not None:
            return value

        value = await db_read_func(**db_kwargs)

        if value is not None:
            ttl = ttl or self._default_ttl
            if isinstance(value, (dict, list)):
                await self.redis.set_json(key, value, ex=ttl)
            else:
                await self.redis.set(key, value, ex=ttl)

            if use_memory:
                self._memory_cache[key] = value

        return value

    async def cache_aside(
        self,
        key: str,
        compute_func: Callable,
        ttl: Optional[int] = None,
        use_memory: bool = True,
        **compute_kwargs,
    ) -> Any:
        value = await self.get(key, use_memory=use_memory)
        if value is not None:
            return value

        value = await compute_func(**compute_kwargs)

        if value is not None:
            ttl = ttl or self._default_ttl
            if isinstance(value, (dict, list)):
                await self.redis.set_json(key, value, ex=ttl)
            else:
                await self.redis.set(key, value, ex=ttl)

            if use_memory:
                self._memory_cache[key] = value

        return value

    async def invalidate(self, key: str):
        await self.delete(key, use_memory=True)

    async def invalidate_pattern(self, pattern: str):
        await self.delete_pattern(pattern)
        keys_to_remove = [k for k in self._memory_cache.keys() if _match_pattern(k, pattern)]
        for k in keys_to_remove:
            del self._memory_cache[k]

    async def warmup(
        self,
        keys_values: Dict[str, Any],
        ttl: Optional[int] = None,
    ):
        for key, value in keys_values.items():
            await self.set(key, value, ttl=ttl, use_memory=True)

    def get_memory_cache_stats(self) -> Dict[str, Any]:
        return {
            "size": len(self._memory_cache),
            "keys": list(self._memory_cache.keys()),
        }

    def clear_memory_cache(self):
        self._memory_cache.clear()


def _match_pattern(key: str, pattern: str) -> bool:
    import re

    regex_pattern = pattern.replace("*", ".*").replace("?", ".")
    return bool(re.match(f"^{regex_pattern}$", key))


_cache_manager: Optional[CacheManager] = None


def get_cache_manager(redis_client: Optional[RedisClient] = None) -> CacheManager:
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager(redis_client)
    return _cache_manager