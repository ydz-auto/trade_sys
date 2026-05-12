"""
Replay Runner - 回放器
从原始数据重新生成聚合K线
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
import asyncio

from infrastructure.logging import get_logger
from infrastructure.database import ClickHouseClient

from ..models.candle_model import Candle, Timeframe
from ..aggregators.candle.candle_aggregator import TimeframeAggregator
from ..publishers.kafka_publisher import KafkaPublisher

logger = get_logger("aggregation_service.replay")


class ReplayRunner:
    """回放运行器

    用于从原始数据重新生成聚合K线
    """

    def __init__(
        self,
        exchange: str,
        symbol: str,
        start_time: int,
        end_time: int,
        source_timeframe: str = "1m"
    ):
        self.exchange = exchange
        self.symbol = symbol
        self.start_time = start_time
        self.end_time = end_time
        self.source_timeframe = Timeframe(source_timeframe)

        self.aggregator = TimeframeAggregator()
        self.publisher: Optional[KafkaPublisher] = None
        self.clickhouse: Optional[ClickHouseClient] = None

        self.stats = {
            "processed": 0,
            "aggregated": 0,
            "published": 0,
            "errors": 0
        }

    async def initialize(self):
        """初始化"""
        self.publisher = KafkaPublisher()
        await self.publisher.initialize()

        self.clickhouse = ClickHouseClient()

    async def run(self):
        """运行回放"""
        logger.info(f"Starting replay: {self.exchange}:{self.symbol} {self.start_time} - {self.end_time}")

        rows = await self._fetch_source_candles()

        for row in rows:
            try:
                candle = self._parse_candle(row)
                results = self.aggregator.process(candle)

                for aggregated in results:
                    await self.publisher.publish_candle(aggregated)
                    self.stats["aggregated"] += 1
                    self.stats["published"] += 1

                self.stats["processed"] += 1

            except Exception as e:
                logger.error(f"Error processing candle: {e}")
                self.stats["errors"] += 1

        logger.info(f"Replay completed: {self.stats}")

    async def _fetch_source_candles(self) -> List:
        """获取源K线"""
        if not self.clickhouse:
            return []

        try:
            rows = await self.clickhouse.execute(
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
                    "exchange": self.exchange,
                    "symbol": self.symbol,
                    "timeframe": self.source_timeframe.value,
                    "start_time": self.start_time,
                    "end_time": self.end_time
                }
            )
            return rows
        except Exception as e:
            logger.error(f"Failed to fetch candles: {e}")
            return []

    def _parse_candle(self, row) -> Candle:
        """解析K线"""
        return Candle(
            exchange=row[0],
            symbol=row[1],
            timeframe=Timeframe(row[2]),
            open_time=row[3],
            close_time=row[5],
            open=float(row[6]),
            high=float(row[7]),
            low=float(row[8]),
            close=float(row[9]),
            volume=float(row[10]),
            quote_volume=float(row[11]),
            trade_count=int(row[12]),
            is_closed=bool(row[13]),
        )

    async def shutdown(self):
        """关闭"""
        if self.publisher:
            await self.publisher.shutdown()


async def run_replay(
    exchange: str,
    symbol: str,
    start_time: int,
    end_time: int,
    source_timeframe: str = "1m"
):
    """运行回放"""
    runner = ReplayRunner(
        exchange=exchange,
        symbol=symbol,
        start_time=start_time,
        end_time=end_time,
        source_timeframe=source_timeframe
    )

    await runner.initialize()
    await runner.run()
    await runner.shutdown()
