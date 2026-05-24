"""
PostgreSQL 连接管理
"""

import asyncio
from typing import Optional, Dict, List, Any, Tuple
from contextlib import asynccontextmanager
import asyncpg
from dataclasses import dataclass

from infrastructure.persistence.database.configs import DatabaseConfig

try:
    from domain.schemas import POSTGRESQL_SCHEMAS
except Exception:
    POSTGRESQL_SCHEMAS = {}


@dataclass
class QueryResult:
    rows: List[Any]
    fields: List[str]
    rowcount: int

    def __iter__(self):
        return iter(self.rows)

    def dicts(self) -> List[Dict[str, Any]]:
        if not self.fields:
            return []
        return [dict(zip(self.fields, row)) for row in self.rows]


class PostgresManager:
    def __init__(self, config: Optional[DatabaseConfig] = None):
        self.config = config or DatabaseConfig()
        self._pool: Optional[asyncpg.Pool] = None
        self._connected = False

    async def connect(self) -> None:
        if self._connected:
            return

        self._pool = await asyncpg.create_pool(
            host=self.config.host,
            port=self.config.port,
            user=self.config.username,
            password=self.config.password,
            database=self.config.database,
            min_size=self.config.min_connections,
            max_size=self.config.max_connections,
            command_timeout=self.config.command_timeout,
        )
        self._connected = True

    async def disconnect(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None
            self._connected = False

    @asynccontextmanager
    async def acquire(self):
        if not self._pool:
            await self.connect()
        async with self._pool.acquire() as connection:
            yield connection

    @asynccontextmanager
    async def transaction(self):
        async with self.acquire() as conn:
            async with conn.transaction():
                yield conn

    async def execute(
        self,
        query: str,
        *args,
        timeout: Optional[float] = None,
    ) -> str:
        async with self.acquire() as conn:
            return await conn.execute(query, *args, timeout=timeout)

    async def fetch(
        self,
        query: str,
        *args,
        timeout: Optional[float] = None,
    ) -> List[asyncpg.Record]:
        async with self.acquire() as conn:
            return await conn.fetch(query, *args, timeout=timeout)

    async def fetchrow(
        self,
        query: str,
        *args,
        timeout: Optional[float] = None,
    ) -> Optional[asyncpg.Record]:
        async with self.acquire() as conn:
            return await conn.fetchrow(query, *args, timeout=timeout)

    async def fetchval(
        self,
        query: str,
        *args,
        timeout: Optional[float] = None,
    ) -> Any:
        async with self.acquire() as conn:
            return await conn.fetchval(query, *args, timeout=timeout)

    async def execute_many(
        self,
        query: str,
        values: List[Tuple],
    ) -> None:
        async with self.acquire() as conn:
            await conn.executemany(query, values)

    async def init_schema(self) -> None:
        for table_name, schema_sql in POSTGRESQL_SCHEMAS.items():
            try:
                await self.execute(schema_sql)
            except Exception as e:
                print(f"Error initializing {table_name}: {e}")

    async def health_check(self) -> bool:
        try:
            result = await self.fetchval("SELECT 1")
            return result == 1
        except Exception:
            return False

    @property
    def is_connected(self) -> bool:
        return self._connected


_postgres_manager: Optional[PostgresManager] = None


def get_postgres_manager(config: Optional[DatabaseConfig] = None) -> PostgresManager:
    global _postgres_manager
    if _postgres_manager is None:
        _postgres_manager = PostgresManager(config)
    return _postgres_manager


async def init_postgres(config: Optional[DatabaseConfig] = None) -> PostgresManager:
    manager = get_postgres_manager(config)
    await manager.connect()
    return manager


async def close_postgres() -> None:
    global _postgres_manager
    if _postgres_manager:
        await _postgres_manager.disconnect()
        _postgres_manager = None
