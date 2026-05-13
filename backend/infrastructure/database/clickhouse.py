"""
ClickHouse 连接管理
"""

import asyncio
import threading
from typing import Optional, Dict, List, Any, Set
from contextlib import asynccontextmanager
from dataclasses import dataclass
import json
import queue
import time

from infrastructure.database.configs import ClickHouseConfig
from infrastructure.database.schemas import CLICKHOUSE_SCHEMAS
from infrastructure.logging import get_logger

logger = get_logger("infrastructure.database.clickhouse")

# 允许的表名白名单 - 防止SQL注入
ALLOWED_TABLES: Set[str] = {
    'klines', 'features', 'factors', 'trades', 'orders',
    'signals', 'events', 'positions', 'audit_logs',
    'execution_records', 'idempotency_records',
}


class ClickHouseConnectionPool:
    """ClickHouse 连接池"""
    
    def __init__(
        self,
        config: ClickHouseConfig,
        max_size: int = 20,
        min_size: int = 5,
        idle_timeout: float = 300.0,
    ):
        self.config = config
        self.max_size = max_size
        self.min_size = min_size
        self.idle_timeout = idle_timeout
        
        self._pool: queue.Queue = queue.Queue(maxsize=max_size)
        self._lock = threading.Lock()
        self._created = 0
        self._closed = False
        
        self._host = config.host
        self._port = config.port
        self._database = config.database
        self._username = config.username
        self._password = config.password
        
    def _create_connection(self):
        """创建新的ClickHouse连接"""
        import clickhouse_driver
        
        conn = clickhouse_driver.Client(
            host=self._host,
            port=self._port,
            database=self._database,
            user=self._username,
            password=self._password,
        )
        self._created += 1
        logger.debug(f"Created new ClickHouse connection (total: {self._created})")
        return conn
    
    def get_connection(self):
        """从池中获取连接"""
        if self._closed:
            raise RuntimeError("Connection pool is closed")
            
        try:
            return self._pool.get_nowait()
        except queue.Empty:
            with self._lock:
                if self._created < self.max_size:
                    return self._create_connection()
            return self._pool.get()
    
    def return_connection(self, conn):
        """归还连接到池"""
        if self._closed:
            try:
                conn.disconnect()
            except:
                pass
            return
            
        try:
            self._pool.put_nowait(conn)
        except queue.Full:
            try:
                conn.disconnect()
            except:
                pass
    
    def close_all(self):
        """关闭所有连接"""
        self._closed = True
        count = 0
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                try:
                    conn.disconnect()
                    count += 1
                except:
                    pass
            except queue.Empty:
                break
        logger.info(f"Closed {count} ClickHouse connections")


class ClickHouseClient:
    def __init__(self, config: ClickHouseConfig):
        self.config = config
        self._pool = ClickHouseConnectionPool(
            config,
            max_size=getattr(config, 'max_connections', 20),
            min_size=getattr(config, 'min_connections', 5),
        )
        
    @staticmethod
    def _validate_table_name(table: str) -> bool:
        """验证表名是否在白名单中"""
        if table not in ALLOWED_TABLES:
            raise ValueError(f"Table name '{table}' is not allowed")
        return True
    
    @staticmethod
    def _validate_column_name(column: str) -> bool:
        """验证列名是否合法"""
        if not column.isidentifier() and column not in ALLOWED_TABLES:
            # 基本验证，防止SQL注入
            import re
            if not re.match(r'^[a-zA-Z0-9_]+$', column):
                raise ValueError(f"Invalid column name: {column}")
        return True

    async def execute(self, query: str) -> None:
        import clickhouse_driver
        
        client = self._pool.get_connection()
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, client.execute, query
            )
        finally:
            self._pool.return_connection(client)

    async def fetch(self, query: str) -> List[Dict[str, Any]]:
        import clickhouse_driver
        
        client = self._pool.get_connection()
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None, client.execute, query
            )
            
            if not result:
                return []

            columns = result[0] if len(result) > 1 else []
            data = result[1] if len(result) > 1 else result[0]

            if not columns or not data:
                return []

            if isinstance(data[0], (tuple, list)):
                return [dict(zip(columns, row)) for row in data]
            else:
                return [dict(zip(columns, [data]))]
        finally:
            self._pool.return_connection(client)

    async def insert(
        self,
        table: str,
        data: List[Dict[str, Any]],
    ) -> None:
        if not data:
            return
            
        # 验证表名
        self._validate_table_name(table)
        
        import clickhouse_driver
        
        client = self._pool.get_connection()
        try:
            columns = list(data[0].keys())
            # 验证列名
            for col in columns:
                self._validate_column_name(col)
                
            values = [tuple(row.get(col) for col in columns) for row in data]

            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.execute(
                    f"INSERT INTO {table} ({','.join(columns)}) VALUES",
                    values,
                ),
            )
        finally:
            self._pool.return_connection(client)

    async def insert_json_each_row(
        self,
        table: str,
        data: List[Dict[str, Any]],
    ) -> None:
        if not data:
            return
            
        # 验证表名
        self._validate_table_name(table)
        
        import clickhouse_driver
        
        client = self._pool.get_connection()
        try:
            json_data = "\n".join(json.dumps(row) for row in data)

            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.execute(
                    f"INSERT INTO {table} FORMAT JSONEachRow",
                    json_data,
                ),
            )
        finally:
            self._pool.return_connection(client)
            
    async def close(self):
        """关闭连接池"""
        self._pool.close_all()


class ClickHouseManager:
    def __init__(self, config: Optional[ClickHouseConfig] = None):
        self.config = config or ClickHouseConfig()
        self._client: Optional[ClickHouseClient] = None

    @property
    def client(self) -> ClickHouseClient:
        if self._client is None:
            self._client = ClickHouseClient(self.config)
        return self._client

    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        if self._client:
            await self._client.close()
        self._client = None

    async def execute(self, query: str) -> None:
        return await self.client.execute(query)

    async def fetch(self, query: str) -> List[Dict[str, Any]]:
        return await self.client.fetch(query)

    async def insert(
        self,
        table: str,
        data: List[Dict[str, Any]],
    ) -> None:
        return await self.client.insert(table, data)

    async def insert_json_each_row(
        self,
        table: str,
        data: List[Dict[str, Any]],
    ) -> None:
        return await self.client.insert_json_each_row(table, data)

    async def init_tables(self) -> None:
        for table_name, schema_sql in CLICKHOUSE_SCHEMAS.items():
            try:
                await self.execute(schema_sql)
            except Exception as e:
                print(f"Error initializing {table_name}: {e}")

    async def health_check(self) -> bool:
        try:
            result = await self.fetch("SELECT 1")
            return True
        except Exception:
            return False

    async def insert_kline(
        self,
        symbol: str,
        timeframe: str,
        open_time: int,
        close_time: int,
        open: float,
        high: float,
        low: float,
        close: float,
        volume: float,
        quote_volume: float,
        trades: int,
    ) -> None:
        await self.insert(
            "klines",
            [
                {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "open_time": open_time,
                    "close_time": close_time,
                    "open": open,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": volume,
                    "quote_volume": quote_volume,
                    "trades": trades,
                }
            ],
        )

    async def insert_feature(
        self,
        symbol: str,
        timestamp: int,
        features: Dict[str, float],
    ) -> None:
        data = {"symbol": symbol, "timestamp": timestamp, **features}
        await self.insert("features", [data])

    async def insert_factor(
        self,
        symbol: str,
        timestamp: int,
        factors: Dict[str, float],
        regime: str,
        confidence: float,
    ) -> None:
        data = {
            "symbol": symbol,
            "timestamp": timestamp,
            **factors,
            "regime": regime,
            "confidence": confidence,
        }
        await self.insert("factors", [data])


_clickhouse_manager: Optional[ClickHouseManager] = None


def get_clickhouse_manager(
    config: Optional[ClickHouseConfig] = None,
) -> ClickHouseManager:
    global _clickhouse_manager
    if _clickhouse_manager is None:
        _clickhouse_manager = ClickHouseManager(config)
    return _clickhouse_manager


async def init_clickhouse(
    config: Optional[ClickHouseConfig] = None,
) -> ClickHouseManager:
    manager = get_clickhouse_manager(config)
    await manager.connect()
    return manager


async def close_clickhouse() -> None:
    global _clickhouse_manager
    if _clickhouse_manager:
        await _clickhouse_manager.disconnect()
        _clickhouse_manager = None