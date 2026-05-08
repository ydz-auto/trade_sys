"""
缓存配置和常量
从 shared.config 导入
"""

from typing import Optional
from dataclasses import dataclass

from shared.config.enums import CacheStrategy
from shared.config.defaults.infrastructure import (
    CACHE_CONFIGS,
    CACHE_TTL,
    CACHE_DB_ALLOCATION,
    KEY_NAMING_CONVENTION,
    CACHE_KEY_PATTERNS,
    DEFAULT_TTL,
)

CACHE_KEY_PREFIX = CACHE_CONFIGS.get("cache.key_prefix", "tradeagent")


@dataclass
class CacheConfig:
    host: str = CACHE_CONFIGS.get("cache.host", "localhost")
    port: int = CACHE_CONFIGS.get("cache.port", 6379)
    db: int = CACHE_CONFIGS.get("cache.db", 0)
    password: Optional[str] = CACHE_CONFIGS.get("cache.password")
    max_connections: int = CACHE_CONFIGS.get("cache.max_connections", 50)
    socket_timeout: float = CACHE_CONFIGS.get("cache.socket_timeout", 5.0)
    socket_connect_timeout: float = CACHE_CONFIGS.get("cache.socket_connect_timeout", 5.0)
    retry_on_timeout: bool = CACHE_CONFIGS.get("cache.retry_on_timeout", True)


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