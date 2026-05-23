from typing import Any, Dict, Optional
from domain.logging import get_logger

logger = get_logger(__name__)


async def get_redis_value(key: str) -> Optional[str]:
    from infrastructure.cache.redis_client import get_redis_client
    client = get_redis_client()
    if client:
        return await client.get(key)
    return None


async def set_redis_value(key: str, value: str, ttl: Optional[int] = None) -> bool:
    from infrastructure.cache.redis_client import get_redis_client
    client = get_redis_client()
    if client:
        if ttl:
            await client.setex(key, ttl, value)
        else:
            await client.set(key, value)
        return True
    return False


async def get_redis_client():
    from infrastructure.cache.redis_client import get_redis_client
    return get_redis_client()


async def init_redis():
    from infrastructure.cache.redis_client import init_redis
    return await init_redis()


def get_redis_client_sync():
    from infrastructure.cache import get_redis_client
    return get_redis_client()


def get_ws_gateway():
    from infrastructure.websocket.gateway import get_ws_gateway
    return get_ws_gateway()
