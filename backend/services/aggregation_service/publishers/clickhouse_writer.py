"""
ClickHouse Writer - ClickHouse 写入器
将聚合后的K线写入 ClickHouse
"""

from typing import Optional, List
from datetime import datetime

from infrastructure.logging import get_logger
from infrastructure.database import ClickHouseClient

from ..models.candle_model import Candle

logger = get_logger("aggregation_service.clickhouse")


class ClickHouseWriter:
    """ClickHouse 写入器"""

    def __init__(self):
        self.client: Optional[ClickHouseClient] = None

    async def initialize(self):
        """初始化"""
        self.client = ClickHouseClient()

    async def create_table(self):
        """创建表"""
        if not self.client:
            return

        sql = """
        CREATE TABLE IF NOT EXISTS candles (
            exchange String,
            symbol String,
            timeframe String,
            open_time UInt64,
            open_time_dt DateTime,
            close_time UInt64,
            open Float64,
            high Float64,
            low Float64,
            close Float64,
            volume Float64,
            quote_volume Float64,
            trade_count UInt32,
            is_closed UInt8,
            is_complete UInt8,
            missing_count UInt16
        )
        ENGINE = ReplacingMergeTree()
        ORDER BY (exchange, symbol, timeframe, open_time)
        """

        try:
            await self.client.execute(sql)
            logger.info("Created candles table")
        except Exception as e:
            logger.error(f"Failed to create table: {e}")

    async def insert_candle(self, candle: Candle):
        """插入单根 K线"""
        if not self.client:
            return

        try:
            await self.client.execute(
                """
                INSERT INTO candles (
                    exchange, symbol, timeframe,
                    open_time, open_time_dt, close_time,
                    open, high, low, close,
                    volume, quote_volume, trade_count,
                    is_closed, is_complete, missing_count
                ) VALUES
                """,
                [candle.to_clickhouse_row()]
            )
            logger.debug(f"Inserted candle: {candle.symbol} {candle.timeframe}")
        except Exception as e:
            logger.error(f"Failed to insert candle: {e}")

    async def insert_candles(self, candles: List[Candle]):
        """批量插入 K线"""
        if not self.client or not candles:
            return

        try:
            rows = [c.to_clickhouse_row() for c in candles]
            await self.client.execute(
                """
                INSERT INTO candles (
                    exchange, symbol, timeframe,
                    open_time, open_time_dt, close_time,
                    open, high, low, close,
                    volume, quote_volume, trade_count,
                    is_closed, is_complete, missing_count
                ) VALUES
                """,
                rows
            )
            logger.info(f"Inserted {len(candles)} candles")
        except Exception as e:
            logger.error(f"Failed to insert candles: {e}")

    async def get_candles(
        self,
        exchange: str,
        symbol: str,
        timeframe: str,
        start_time: int,
        end_time: int
    ) -> List[Candle]:
        """查询 K线"""
        if not self.client:
            return []

        try:
            rows = await self.client.execute(
                """
                SELECT * FROM candles
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
                    "end_time": end_time
                }
            )

            candles = []
            for row in rows:
                candles.append(Candle(
                    exchange=row[0],
                    symbol=row[1],
                    timeframe=row[2],
                    open_time=row[3],
                    close_time=row[5],
                    open=row[6],
                    high=row[7],
                    low=row[8],
                    close=row[9],
                    volume=row[10],
                    quote_volume=row[11],
                    trade_count=row[12],
                    is_closed=bool(row[13]),
                ))

            return candles
        except Exception as e:
            logger.error(f"Failed to get candles: {e}")
            return []

    async def shutdown(self):
        """关闭"""
        if self.client:
            await self.client.close()


_writer: Optional[ClickHouseWriter] = None


async def get_clickhouse_writer() -> ClickHouseWriter:
    """获取 ClickHouse 写入器"""
    global _writer
    if _writer is None:
        _writer = ClickHouseWriter()
        await _writer.initialize()
    return _writer
