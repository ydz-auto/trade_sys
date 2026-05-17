"""
缓存管理器
支持多种缓存策略
"""

import asyncio
from typing import Optional, Dict, List, Any, Callable
from datetime import datetime
from collections import OrderedDict
import json

from infrastructure.cache.redis_client import RedisClient, get_redis_client
from infrastructure.cache.config import (
    CACHE_TTL,
    DEFAULT_TTL,
    CacheStrategy,
    CACHE_KEY_PREFIX,
)
from infrastructure.cache.keys import CacheKey, KeyPattern


class LRUMemoryCache:
    def __init__(self, max_size: int = 1000):
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self._max_size = max_size

    def get(self, key: str) -> Any:
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def set(self, key: str, value: Any) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        if len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

    def delete(self, key: str) -> bool:
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def clear(self) -> None:
        self._cache.clear()

    def keys(self) -> List[str]:
        return list(self._cache.keys())

    def __len__(self) -> int:
        return len(self._cache)

    def __contains__(self, key: str) -> bool:
        return key in self._cache


class CacheManager:
    def __init__(self, redis_client: Optional[RedisClient] = None, max_memory_items: int = 1000):
        self.redis = redis_client or get_redis_client()
        self._memory_cache = LRUMemoryCache(max_size=max_memory_items)
        self._default_ttl = DEFAULT_TTL

    def set_default_ttl(self, ttl: int):
        self._default_ttl = ttl

    async def get(
        self,
        key: str,
        default: Any = None,
        use_memory: bool = True,
    ) -> Any:
        if use_memory:
            cached = self._memory_cache.get(key)
            if cached is not None:
                return cached

        value = await self.redis.get(key)
        if value is None:
            return default

        try:
            result = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            result = value

        if use_memory:
            self._memory_cache.set(key, result)

        return result

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        use_memory: bool = True,
    ) -> bool:
        if use_memory:
            self._memory_cache.set(key, value)

        ttl = ttl or self._default_ttl

        if isinstance(value, (dict, list)):
            return await self.redis.set_json(key, value, ex=ttl)
        else:
            return await self.redis.set(key, value, ex=ttl)

    async def delete(self, key: str, use_memory: bool = True) -> int:
        if use_memory:
            self._memory_cache.delete(key)

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
                self._memory_cache.set(key, value)

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
                self._memory_cache.set(key, value)

        return value

    async def invalidate(self, key: str):
        await self.delete(key, use_memory=True)

    async def invalidate_pattern(self, pattern: str):
        await self.delete_pattern(pattern)
        keys_to_remove = [k for k in self._memory_cache.keys() if _match_pattern(k, pattern)]
        for k in keys_to_remove:
            self._memory_cache.delete(k)

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