"""
Redis 客户端封装
"""

import json
import asyncio
from typing import Optional, Dict, List, Any, Union
from dataclasses import dataclass
import redis.asyncio as aioredis

from infrastructure.cache.config import CacheConfig, CACHE_KEY_PREFIX, DEFAULT_TTL


@dataclass
class RedisConnection:
    host: str
    port: int
    db: int
    password: Optional[str]


class RedisClient:
    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or CacheConfig()
        self._client: Optional[aioredis.Redis] = None
        self._connected = False

    async def connect(self) -> None:
        if self._connected:
            return

        self._client = await aioredis.from_url(
            f"redis://{self.config.host}:{self.config.port}/{self.config.db}",
            password=self.config.password,
            max_connections=self.config.max_connections,
            socket_timeout=self.config.socket_timeout,
            socket_connect_timeout=self.config.socket_connect_timeout,
            decode_responses=True,
        )
        self._connected = True

    async def disconnect(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None
            self._connected = False

    @property
    def client(self) -> aioredis.Redis:
        if not self._client or not self._connected:
            raise RuntimeError("Redis client not connected")
        return self._client

    async def ping(self) -> bool:
        try:
            return await self.client.ping()
        except Exception:
            return False

    async def get(self, key: str) -> Optional[str]:
        return await self.client.get(key)

    async def set(
        self,
        key: str,
        value: Union[str, int, float],
        ex: Optional[int] = None,
    ) -> bool:
        return await self.client.set(key, str(value), ex=ex)

    async def setex(self, key: str, seconds: int, value: Union[str, int, float]) -> bool:
        return await self.client.setex(key, seconds, str(value))

    async def set_json(
        self,
        key: str,
        value: Dict[str, Any],
        ex: Optional[int] = None,
    ) -> bool:
        return await self.client.set(key, json.dumps(value), ex=ex)

    async def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        data = await self.client.get(key)
        if data:
            return json.loads(data)
        return None

    async def delete(self, key: str) -> int:
        return await self.client.delete(key)

    async def delete_pattern(self, pattern: str, batch_size: int = 100) -> int:
        deleted = 0
        cursor = 0
        while True:
            cursor, keys = await self.client.scan(cursor, match=pattern, count=batch_size)
            if keys:
                deleted += await self.client.delete(*keys)
            if cursor == 0:
                break
        return deleted

    async def exists(self, key: str) -> bool:
        return await self.client.exists(key) > 0

    async def incr(self, key: str) -> int:
        return await self.client.incr(key)

    async def decr(self, key: str) -> int:
        return await self.client.decr(key)

    async def expire(self, key: str, seconds: int) -> bool:
        return await self.client.expire(key, seconds)

    async def ttl(self, key: str) -> int:
        return await self.client.ttl(key)

    async def hset(self, name: str, key: str, value: Union[str, int, float]) -> int:
        return await self.client.hset(name, key, str(value))

    async def hget(self, name: str, key: str) -> Optional[str]:
        return await self.client.hget(name, key)

    async def hgetall(self, name: str) -> Dict[str, str]:
        return await self.client.hgetall(name)

    async def hmset(self, name: str, mapping: Dict[str, Any]) -> bool:
        return await self.client.hmset(name, mapping)

    async def hdel(self, name: str, *keys: str) -> int:
        return await self.client.hdel(name, *keys)

    async def hincrby(self, name: str, key: str, amount: int = 1) -> int:
        return await self.client.hincrby(name, key, amount)

    async def lpush(self, key: str, *values: Any) -> int:
        return await self.client.lpush(key, *[str(v) for v in values])

    async def rpush(self, key: str, *values: Any) -> int:
        return await self.client.rpush(key, *[str(v) for v in values])

    async def lrange(self, key: str, start: int = 0, end: int = -1) -> List[str]:
        return await self.client.lrange(key, start, end)

    async def ltrim(self, key: str, start: int, end: int) -> bool:
        """裁剪列表，只保留指定范围内的元素"""
        return await self.client.ltrim(key, start, end)

    async def lpop(self, key: str) -> Optional[str]:
        return await self.client.lpop(key)

    async def rpop(self, key: str) -> Optional[str]:
        return await self.client.rpop(key)

    async def llen(self, key: str) -> int:
        return await self.client.llen(key)

    async def sadd(self, key: str, *values: Any) -> int:
        return await self.client.sadd(key, *[str(v) for v in values])

    async def smembers(self, key: str) -> set:
        return await self.client.smembers(key)

    async def sismember(self, key: str, value: Any) -> bool:
        return await self.client.sismember(key, str(value))

    async def srem(self, key: str, *values: Any) -> int:
        return await self.client.srem(key, *[str(v) for v in values])

    async def zadd(self, key: str, mapping: Dict[str, Any]) -> int:
        return await self.client.zadd(key, mapping)

    async def zrange(
        self,
        key: str,
        start: int = 0,
        end: int = -1,
        withscores: bool = False,
    ) -> List[Any]:
        return await self.client.zrange(key, start, end, withscores=withscores)

    async def zrevrange(
        self,
        key: str,
        start: int = 0,
        end: int = -1,
        withscores: bool = False,
    ) -> List[Any]:
        return await self.client.zrevrange(key, start, end, withscores=withscores)

    async def zrangebyscore(
        self,
        key: str,
        min_score: Union[str, int],
        max_score: Union[str, int],
        withscores: bool = False,
    ) -> List[Any]:
        return await self.client.zrangebyscore(
            key, min_score, max_score, withscores=withscores
        )

    async def publish(self, channel: str, message: Any) -> int:
        return await self.client.publish(channel, str(message))

    async def get_redis_info(self) -> Dict[str, Any]:
        info = await self.client.info()
        return dict(info)

    @property
    def is_connected(self) -> bool:
        return self._connected


_redis_client: Optional[RedisClient] = None


def get_redis_client(config: Optional[CacheConfig] = None) -> RedisClient:
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient(config)
    return _redis_client


async def init_redis(config: Optional[CacheConfig] = None) -> RedisClient:
    client = get_redis_client(config)
    await client.connect()
    return client


async def close_redis() -> None:
    global _redis_client
    if _redis_client:
        await _redis_client.disconnect()
        _redis_client = None