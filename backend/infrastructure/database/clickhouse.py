"""
ClickHouse 连接管理
"""

import asyncio
from typing import Optional, Dict, List, Any
from contextlib import asynccontextmanager
from dataclasses import dataclass
import json

from infrastructure.database.configs import ClickHouseConfig
from infrastructure.database.schemas import CLICKHOUSE_SCHEMAS


class ClickHouseClient:
    def __init__(self, config: ClickHouseConfig):
        self.config = config
        self._host = config.host
        self._port = config.port
        self._database = config.database
        self._username = config.username
        self._password = config.password

    async def execute(self, query: str) -> None:
        import clickhouse_driver

        client = clickhouse_driver.Client(
            host=self._host,
            port=self._port,
            database=self._database,
            user=self._username,
            password=self._password,
        )
        await asyncio.get_event_loop().run_in_executor(
            None, client.execute, query
        )
        client.disconnect()

    async def fetch(self, query: str) -> List[Dict[str, Any]]:
        import clickhouse_driver

        client = clickhouse_driver.Client(
            host=self._host,
            port=self._port,
            database=self._database,
            user=self._username,
            password=self._password,
        )
        result = await asyncio.get_event_loop().run_in_executor(
            None, client.execute, query
        )
        client.disconnect()

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

    async def insert(
        self,
        table: str,
        data: List[Dict[str, Any]],
    ) -> None:
        if not data:
            return

        import clickhouse_driver

        client = clickhouse_driver.Client(
            host=self._host,
            port=self._port,
            database=self._database,
            user=self._username,
            password=self._password,
        )

        columns = list(data[0].keys())
        values = [tuple(row.get(col) for col in columns) for row in data]

        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: client.execute(
                f"INSERT INTO {table} ({','.join(columns)}) VALUES",
                values,
            ),
        )
        client.disconnect()

    async def insert_json_each_row(
        self,
        table: str,
        data: List[Dict[str, Any]],
    ) -> None:
        if not data:
            return

        import clickhouse_driver

        client = clickhouse_driver.Client(
            host=self._host,
            port=self._port,
            database=self._database,
            user=self._username,
            password=self._password,
        )

        json_data = "\n".join(json.dumps(row) for row in data)

        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: client.execute(
                f"INSERT INTO {table} FORMAT JSONEachRow",
                json_data,
            ),
        )
        client.disconnect()


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