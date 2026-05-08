"""
TradeAgent Database Module
数据库连接模块
支持 PostgreSQL (SQLAlchemy + asyncpg) 和 ClickHouse
"""

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrastructure.database.enums import (
        DatabaseType, PoolType, TransactionIsolation, QueryMode,
    )
    from infrastructure.database.configs import (
        DatabaseConfig, ClickHouseConfig, RedisConfig, PoolConfig,
    )
    from infrastructure.database.postgresql import PostgresManager, get_postgres_manager
    from infrastructure.database.clickhouse import ClickHouseManager, get_clickhouse_manager
    from infrastructure.database.connection_pool import ConnectionPool
    from infrastructure.database.sqlalchemy_base import Base, SQLAlchemyManager, get_sqlalchemy_manager, init_sqlalchemy, close_sqlalchemy
    from infrastructure.database.models import User, Role, APIKey, TradingAccount, Position, Order


def __getattr__(name):
    """Lazy import to avoid requiring asyncpg/clickhouse-driver at import time"""
    _module_map = {
        # enums
        "DatabaseType": ("infrastructure.database.enums", "DatabaseType"),
        "PoolType": ("infrastructure.database.enums", "PoolType"),
        "TransactionIsolation": ("infrastructure.database.enums", "TransactionIsolation"),
        "QueryMode": ("infrastructure.database.enums", "QueryMode"),
        # configs
        "DatabaseConfig": ("infrastructure.database.configs", "DatabaseConfig"),
        "ClickHouseConfig": ("infrastructure.database.configs", "ClickHouseConfig"),
        "RedisConfig": ("infrastructure.database.configs", "RedisConfig"),
        "PoolConfig": ("infrastructure.database.configs", "PoolConfig"),
        # postgresql
        "PostgresManager": ("infrastructure.database.postgresql", "PostgresManager"),
        "get_postgres_manager": ("infrastructure.database.postgresql", "get_postgres_manager"),
        # clickhouse
        "ClickHouseManager": ("infrastructure.database.clickhouse", "ClickHouseManager"),
        "get_clickhouse_manager": ("infrastructure.database.clickhouse", "get_clickhouse_manager"),
        # connection pool
        "ConnectionPool": ("infrastructure.database.connection_pool", "ConnectionPool"),
        # sqlalchemy
        "Base": ("infrastructure.database.sqlalchemy_base", "Base"),
        "SQLAlchemyManager": ("infrastructure.database.sqlalchemy_base", "SQLAlchemyManager"),
        "get_sqlalchemy_manager": ("infrastructure.database.sqlalchemy_base", "get_sqlalchemy_manager"),
        "init_sqlalchemy": ("infrastructure.database.sqlalchemy_base", "init_sqlalchemy"),
        "close_sqlalchemy": ("infrastructure.database.sqlalchemy_base", "close_sqlalchemy"),
        # models
        "User": ("infrastructure.database.models", "User"),
        "Role": ("infrastructure.database.models", "Role"),
        "APIKey": ("infrastructure.database.models", "APIKey"),
        "TradingAccount": ("infrastructure.database.models", "TradingAccount"),
        "Position": ("infrastructure.database.models", "Position"),
        "Order": ("infrastructure.database.models", "Order"),
        # schemas
        "POSTGRESQL_SCHEMAS": ("infrastructure.database.schemas", "POSTGRESQL_SCHEMAS"),
        "CLICKHOUSE_SCHEMAS": ("infrastructure.database.schemas", "CLICKHOUSE_SCHEMAS"),
    }

    if name in _module_map:
        module_path, attr_name = _module_map[name]
        try:
            mod = __import__(module_path, fromlist=[attr_name])
            return getattr(mod, attr_name)
        except ImportError as e:
            raise AttributeError(
                f"Cannot import '{name}' from 'infrastructure.database': {e}. "
                f"Install the required package first."
            )

    raise AttributeError(f"module 'infrastructure.database' has no attribute '{name}'")


def __dir__():
    return [
        "DatabaseType", "PoolType", "TransactionIsolation", "QueryMode",
        "DatabaseConfig", "ClickHouseConfig", "RedisConfig", "PoolConfig",
        "PostgresManager", "get_postgres_manager",
        "ClickHouseManager", "get_clickhouse_manager",
        "ConnectionPool",
        "Base", "SQLAlchemyManager", "get_sqlalchemy_manager", "init_sqlalchemy", "close_sqlalchemy",
        "User", "Role", "APIKey", "TradingAccount", "Position", "Order",
        "POSTGRESQL_SCHEMAS", "CLICKHOUSE_SCHEMAS",
    ]


__all__ = list(__dir__())
