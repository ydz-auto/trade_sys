"""
Database 配置 - 基础设施配置
"""

DATABASE_CONFIGS = {
    "database.host": "localhost",
    "database.port": 5432,
    "database.name": "tradeagent",
    "database.username": "postgres",
    "database.password": "postgres",
    "database.min_connections": 5,
    "database.max_connections": 20,
    "database.connection_timeout": 30,
    "database.command_timeout": 60,
}

CLICKHOUSE_CONFIGS = {
    "clickhouse.host": "localhost",
    "clickhouse.port": 9000,
    "clickhouse.database": "tradeagent",
    "clickhouse.username": "default",
    "clickhouse.password": "",
    "clickhouse.min_connections": 5,
    "clickhouse.max_connections": 20,
    "clickhouse.connection_timeout": 30,
    "clickhouse.send_receive_timeout": 300,
}

POOL_CONFIGS = {
    "pool.type": "default",
    "pool.min_size": 5,
    "pool.max_size": 20,
    "pool.max_overflow": 10,
    "pool.recycle": 3600,
    "pool.timeout": 30,
}
