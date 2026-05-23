"""
Database 配置 - 基础设施配置
"""

import os

DATABASE_CONFIGS = {
    "database.host": os.environ.get("DATABASE_HOST", "localhost"),
    "database.port": int(os.environ.get("DATABASE_PORT", "5432")),
    "database.name": os.environ.get("DATABASE_NAME", "tradeagent"),
    "database.username": os.environ.get("DATABASE_USERNAME", "postgres"),
    "database.password": os.environ.get("DATABASE_PASSWORD", "postgres"),
    "database.min_connections": int(os.environ.get("DATABASE_MIN_CONNECTIONS", "5")),
    "database.max_connections": int(os.environ.get("DATABASE_MAX_CONNECTIONS", "20")),
    "database.connection_timeout": int(os.environ.get("DATABASE_CONNECTION_TIMEOUT", "30")),
    "database.command_timeout": int(os.environ.get("DATABASE_COMMAND_TIMEOUT", "60")),
}

CLICKHOUSE_CONFIGS = {
    "clickhouse.host": os.environ.get("CLICKHOUSE_HOST", "localhost"),
    "clickhouse.port": int(os.environ.get("CLICKHOUSE_PORT", "9000")),
    "clickhouse.database": os.environ.get("CLICKHOUSE_DATABASE", "tradeagent"),
    "clickhouse.username": os.environ.get("CLICKHOUSE_USERNAME", "default"),
    "clickhouse.password": os.environ.get("CLICKHOUSE_PASSWORD", ""),
    "clickhouse.min_connections": int(os.environ.get("CLICKHOUSE_MIN_CONNECTIONS", "5")),
    "clickhouse.max_connections": int(os.environ.get("CLICKHOUSE_MAX_CONNECTIONS", "20")),
    "clickhouse.connection_timeout": int(os.environ.get("CLICKHOUSE_CONNECTION_TIMEOUT", "30")),
    "clickhouse.send_receive_timeout": int(os.environ.get("CLICKHOUSE_SEND_RECEIVE_TIMEOUT", "300")),
}

POOL_CONFIGS = {
    "pool.type": os.environ.get("POOL_TYPE", "default"),
    "pool.min_size": int(os.environ.get("POOL_MIN_SIZE", "5")),
    "pool.max_size": int(os.environ.get("POOL_MAX_SIZE", "20")),
    "pool.max_overflow": int(os.environ.get("POOL_MAX_OVERFLOW", "10")),
    "pool.recycle": int(os.environ.get("POOL_RECYCLE", "3600")),
    "pool.timeout": int(os.environ.get("POOL_TIMEOUT", "30")),
}
