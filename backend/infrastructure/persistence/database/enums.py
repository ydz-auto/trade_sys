"""
Database Enums
数据库相关枚举类型
"""

from enum import Enum


class DatabaseType(str, Enum):
    POSTGRESQL = "postgresql"
    CLICKHOUSE = "clickhouse"
    REDIS = "redis"
    MONGODB = "mongodb"


class PoolType(str, Enum):
    PgBouncer = "pgbouncer"
    PgPool = "pgpool"
    ProxySQL = "proxysql"


class TransactionIsolation(str, Enum):
    READ_COMMITTED = "READ COMMITTED"
    REPEATABLE_READ = "REPEATABLE READ"
    SERIALIZABLE = "SERIALIZABLE"


class QueryMode(str, Enum):
    SYNC = "sync"
    ASYNC = "async"
    STREAMING = "streaming"