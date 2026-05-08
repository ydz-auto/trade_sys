"""
Response Cache - LLM响应缓存
"""

import asyncio
import time
from typing import Dict, Optional, Any

from infrastructure.logging import get_logger
logger = get_logger("llm.cache")


class ResponseCache:
    """LLM响应缓存（内存版，可替换为Redis）"""

    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Dict]:
        """获取缓存"""
        async with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                if time.time() < entry["expire_at"]:
                    return entry["data"]
                else:
                    del self._cache[key]
            return None

    async def set(self, key: str, data: Dict, ttl: int = None):
        """设置缓存"""
        async with self._lock:
            if len(self._cache) >= self.max_size:
                await self._evict_oldest()

            self._cache[key] = {
                "data": data,
                "expire_at": time.time() + (ttl or self.default_ttl),
                "created_at": time.time()
            }

    async def delete(self, key: str):
        """删除缓存"""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]

    async def clear(self):
        """清空缓存"""
        async with self._lock:
            self._cache.clear()

    async def size(self) -> int:
        """获取缓存大小"""
        async with self._lock:
            return len(self._cache)

    async def _evict_oldest(self):
        """淘汰最老的条目"""
        if not self._cache:
            return

        oldest_key = min(
            self._cache.keys(),
            key=lambda k: self._cache[k]["created_at"]
        )
        del self._cache[oldest_key]
        logger.debug(f"Evicted oldest cache entry: {oldest_key}")

    async def cleanup_expired(self):
        """清理过期条目"""
        async with self._lock:
            now = time.time()
            expired_keys = [
                k for k, v in self._cache.items()
                if now >= v["expire_at"]
            ]
            for key in expired_keys:
                del self._cache[key]

            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired entries")


class RedisResponseCache:
    """Redis版响应缓存"""

    def __init__(self, redis_url: str = "redis://localhost:6379/0", default_ttl: int = 3600):
        self.redis_url = redis_url
        self.default_ttl = default_ttl
        self._client = None

    async def _get_client(self):
        """获取Redis客户端"""
        if self._client is None:
            import redis.asyncio as redis
            self._client = redis.from_url(self.redis_url, decode_responses=True)
        return self._client

    async def get(self, key: str) -> Optional[Dict]:
        """获取缓存"""
        import json
        client = await self._get_client()
        value = await client.get(f"llm:{key}")
        if value:
            return json.loads(value)
        return None

    async def set(self, key: str, data: Dict, ttl: int = None):
        """设置缓存"""
        import json
        client = await self._get_client()
        await client.setex(
            f"llm:{key}",
            ttl or self.default_ttl,
            json.dumps(data)
        )

    async def delete(self, key: str):
        """删除缓存"""
        client = await self._get_client()
        await client.delete(f"llm:{key}")

    async def clear(self):
        """清空缓存"""
        client = await self._get_client()
        await client.delete(*await client.keys("llm:*"))

    async def size(self) -> int:
        """获取缓存大小"""
        client = await self._get_client()
        return len(await client.keys("llm:*"))
