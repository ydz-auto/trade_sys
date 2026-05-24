"""
缓存配置和常量
从 shared.config 导入
"""

import os
from typing import Optional
from dataclasses import dataclass
from urllib.parse import urlparse

from infrastructure.config.enums import CacheStrategy
from infrastructure.config.defaults.infrastructure import (
    CACHE_CONFIGS,
    CACHE_TTL,
    CACHE_DB_ALLOCATION,
    KEY_NAMING_CONVENTION,
    CACHE_KEY_PATTERNS,
    DEFAULT_TTL,
)

CACHE_KEY_PREFIX = CACHE_CONFIGS.get("cache.key_prefix", "tradeagent")


def _parse_redis_url(url: str) -> tuple:
    """解析 Redis URL，返回 (host, port, db, password)"""
    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 6379
    db = int(parsed.path.lstrip("/")) if parsed.path and parsed.path != "/" else 0
    password = parsed.password
    return host, port, db, password


def _get_redis_config_from_env() -> tuple:
    """从 REDIS_URL 环境变量获取 Redis 配置"""
    redis_url = os.environ.get("REDIS_URL")
    if redis_url:
        return _parse_redis_url(redis_url)
    return None, None, None, None


_env_host, _env_port, _env_db, _env_password = _get_redis_config_from_env()


@dataclass
class CacheConfig:
    host: str = _env_host or CACHE_CONFIGS.get("cache.host", "localhost")
    port: int = _env_port or CACHE_CONFIGS.get("cache.port", 6379)
    db: int = _env_db if _env_db is not None else CACHE_CONFIGS.get("cache.db", 0)
    password: Optional[str] = _env_password if _env_password is not None else CACHE_CONFIGS.get("cache.password")
    max_connections: int = CACHE_CONFIGS.get("cache.max_connections", 50)
    socket_timeout: float = CACHE_CONFIGS.get("cache.socket_timeout", 5.0)
    socket_connect_timeout: float = CACHE_CONFIGS.get("cache.socket_connect_timeout", 5.0)
    retry_on_timeout: bool = CACHE_CONFIGS.get("cache.retry_on_timeout", True)

    @classmethod
    def from_startup_settings(cls) -> "CacheConfig":
        try:
            from infrastructure.config.startup.settings import get_startup_settings
            settings = get_startup_settings()
            return cls(
                host=settings.redis.host,
                port=settings.redis.port,
                db=settings.redis.db,
                password=settings.redis.password,
                max_connections=settings.redis.max_connections,
                socket_timeout=settings.redis.socket_timeout,
                socket_connect_timeout=settings.redis.socket_connect_timeout,
                retry_on_timeout=settings.redis.retry_on_timeout,
            )
        except Exception:
            return cls()


__all__ = [
    "CacheStrategy",
    "CacheConfig",
    "CACHE_KEY_PREFIX",
    "CACHE_TTL",
    "CACHE_DB_ALLOCATION",
    "KEY_NAMING_CONVENTION",
    "CACHE_KEY_PATTERNS",
    "DEFAULT_TTL",
]