"""
Market Data Repository - 市场数据仓储

封装 ClickHouse 中 kline / candle 相关的 SQL 操作，
供 rebuild_manager、gap_detector 等上层服务调用，
避免上层直接写 SQL。
"""

from typing import Dict, List, Optional, Any
from datetime import datetime

from infrastructure.logging import get_logger
from infrastructure.persistence.database.clickhouse import ClickHouseManager

logger = get_logger("infrastructure.persistence.repository.market_data.kline")


class KlineRepository:

    def __init__(self, clickhouse: Optional[ClickHouseManager] = None):
        self._clickhouse = clickhouse

    async def initialize(self, clickhouse: Optional[ClickHouseManager] = None):
        if clickhouse:
            self._clickhouse = clickhouse
        if self._clickhouse is None:
            self._clickhouse = ClickHouseManager()

    @property
    def clickhouse(self) -> ClickHouseManager:
        if self._clickhouse is None:
            raise RuntimeError("KlineRepository not initialized. Call initialize() first.")
        return self._clickhouse

    async def fetch_candles(
        self,
        exchange: str,
        symbol: str,
        timeframe: str,
        start_time: int,
        end_time: int,
    ) -> List[Dict[str, Any]]:
        rows = await self.clickhouse.execute(
            """
            SELECT
                open_time,
                close_time,
                is_complete,
                missing_count
            FROM candles
            WHERE exchange = %(exchange)s
            AND symbol = %(symbol)s
            AND timeframe = %(timeframe)s
            AND open_time >= %(start_time)s
            AND open_time < %(end_time)s
            ORDER BY open_time
            """,
            {
                "exchange": exchange,
                "symbol": symbol,
                "timeframe": timeframe,
                "start_time": start_time,
                "end_time": end_time,
            }
        )

        return [
            {
                "open_time": row[0],
                "close_time": row[1],
                "is_complete": row[2],
                "missing_count": row[3],
            }
            for row in rows
        ]

    async def fetch_klines(
        self,
        exchange: str,
        symbol: str,
        timeframe: str,
        start_time: int,
        end_time: int,
        limit: int = 10000,
    ) -> List[Dict[str, Any]]:
        rows = await self.clickhouse.execute(
            """
            SELECT
                open_time, close_time,
                open, high, low, close,
                volume, quote_volume, trades
            FROM klines
            WHERE exchange = %(exchange)s
            AND symbol = %(symbol)s
            AND timeframe = %(timeframe)s
            AND open_time >= %(start_time)s
            AND open_time < %(end_time)s
            ORDER BY open_time
            LIMIT %(limit)s
            """,
            {
                "exchange": exchange,
                "symbol": symbol,
                "timeframe": timeframe,
                "start_time": start_time,
                "end_time": end_time,
                "limit": limit,
            }
        )

        return [
            {
                "open_time": row[0],
                "close_time": row[1],
                "open": row[2],
                "high": row[3],
                "low": row[4],
                "close": row[5],
                "volume": row[6],
                "quote_volume": row[7],
                "trades": row[8],
            }
            for row in rows
        ]

    async def insert_klines(
        self,
        rows: List[Dict[str, Any]],
        table: str = "klines",
    ) -> int:
        if not rows:
            return 0

        await self.clickhouse.execute(
            f"""
            INSERT INTO {table} (
                open_time, close_time, exchange, symbol, timeframe,
                open, high, low, close,
                volume, quote_volume, trades
            ) VALUES
            """,
            rows
        )
        return len(rows)

    async def get_latest_timestamp(
        self,
        exchange: str,
        symbol: str,
        timeframe: str,
        table: str = "klines",
    ) -> Optional[int]:
        rows = await self.clickhouse.execute(
            f"""
            SELECT max(open_time) FROM {table}
            WHERE exchange = %(exchange)s
            AND symbol = %(symbol)s
            AND timeframe = %(timeframe)s
            """,
            {
                "exchange": exchange,
                "symbol": symbol,
                "timeframe": timeframe,
            }
        )

        if rows and rows[0][0]:
            return rows[0][0]
        return None


_kline_repo: Optional[KlineRepository] = None


async def get_kline_repository() -> KlineRepository:
    global _kline_repo
    if _kline_repo is None:
        _kline_repo = KlineRepository()
        await _kline_repo.initialize()
    return _kline_repo
