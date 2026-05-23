"""
Database Configurations
数据库连接配置
从 shared.config 导入
"""

from typing import Optional
from dataclasses import dataclass

from infrastructure.config.defaults.infrastructure import DATABASE_CONFIGS, CLICKHOUSE_CONFIGS, POOL_CONFIGS
from infrastructure.config.defaults.infrastructure.cache import CACHE_CONFIGS


@dataclass
class RedisConfig:
    host: str = CACHE_CONFIGS.get("cache.host", "localhost")
    port: int = CACHE_CONFIGS.get("cache.port", 6379)
    db: int = CACHE_CONFIGS.get("cache.db", 0)
    password: Optional[str] = CACHE_CONFIGS.get("cache.password")
    max_connections: int = CACHE_CONFIGS.get("cache.max_connections", 50)
    socket_timeout: float = CACHE_CONFIGS.get("cache.socket_timeout", 5.0)
    socket_connect_timeout: float = CACHE_CONFIGS.get("cache.socket_connect_timeout", 5.0)
    retry_on_timeout: bool = CACHE_CONFIGS.get("cache.retry_on_timeout", True)
    key_prefix: str = CACHE_CONFIGS.get("cache.key_prefix", "tradeagent")
    default_ttl: int = CACHE_CONFIGS.get("cache.default_ttl", 60)


@dataclass
class DatabaseConfig:
    host: str = DATABASE_CONFIGS.get("database.host", "localhost")
    port: int = DATABASE_CONFIGS.get("database.port", 5432)
    database: str = DATABASE_CONFIGS.get("database.name", "tradeagent")
    username: str = DATABASE_CONFIGS.get("database.username", "postgres")
    password: str = DATABASE_CONFIGS.get("database.password", "postgres")
    min_connections: int = DATABASE_CONFIGS.get("database.min_connections", 5)
    max_connections: int = DATABASE_CONFIGS.get("database.max_connections", 20)
    connection_timeout: int = DATABASE_CONFIGS.get("database.connection_timeout", 30)
    command_timeout: int = DATABASE_CONFIGS.get("database.command_timeout", 60)

    def get_async_url(self) -> str:
        return f"postgresql+asyncpg://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"


@dataclass
class ClickHouseConfig:
    host: str = CLICKHOUSE_CONFIGS.get("clickhouse.host", "localhost")
    port: int = CLICKHOUSE_CONFIGS.get("clickhouse.port", 9000)
    database: str = CLICKHOUSE_CONFIGS.get("clickhouse.database", "tradeagent")
    username: str = CLICKHOUSE_CONFIGS.get("clickhouse.username", "default")
    password: str = CLICKHOUSE_CONFIGS.get("clickhouse.password", "")
    min_connections: int = CLICKHOUSE_CONFIGS.get("clickhouse.min_connections", 5)
    max_connections: int = CLICKHOUSE_CONFIGS.get("clickhouse.max_connections", 20)
    connection_timeout: int = CLICKHOUSE_CONFIGS.get("clickhouse.connection_timeout", 30)
    send_receive_timeout: int = CLICKHOUSE_CONFIGS.get("clickhouse.send_receive_timeout", 300)


@dataclass
class PoolConfig:
    pool_type: str = POOL_CONFIGS.get("pool.type", "default")
    min_size: int = POOL_CONFIGS.get("pool.min_size", 5)
    max_size: int = POOL_CONFIGS.get("pool.max_size", 20)
    max_overflow: int = POOL_CONFIGS.get("pool.max_overflow", 10)
    pool_recycle: int = POOL_CONFIGS.get("pool.recycle", 3600)
    pool_timeout: int = POOL_CONFIGS.get("pool.timeout", 30)


__all__ = [
    "DatabaseConfig",
    "ClickHouseConfig",
    "PoolConfig",
]