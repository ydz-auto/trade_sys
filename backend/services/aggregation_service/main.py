"""
Aggregation Service - K线聚合服务
主入口
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from infrastructure.logging import get_logger
logger = get_logger("aggregation_service.main")

from shared.config import get_datasource_config_manager
from shared.state import get_system_state_manager

from .aggregators.candle.candle_aggregator import get_timeframe_aggregator
from .aggregators.trade.trade_aggregator import get_trade_aggregator
from .aggregators.orderbook.orderbook_aggregator import get_orderbook_aggregator
from .publishers.kafka_publisher import get_kafka_publisher
from .publishers.clickhouse_writer import get_clickhouse_writer
from .state.state_manager import get_window_state_manager
from .models.candle_model import Candle, Timeframe
from .models.trade_model import Trade
from .models.orderbook_model import OrderBookSnapshot

SERVICE_NAME = "aggregation_service"


class AggregationService:
    """聚合服务"""

    def __init__(self):
        self.timeframe_aggregator = get_timeframe_aggregator()
        self.trade_aggregator = get_trade_aggregator()
        self.orderbook_aggregator = get_orderbook_aggregator()

        self.publisher: Optional[KafkaPublisher] = None
        self.writer: Optional[ClickHouseWriter] = None
        self.state_manager = get_window_state_manager()

        self._running = False
        self._stats = {
            "candles_processed": 0,
            "candles_aggregated": 0,
            "trades_processed": 0,
            "trades_aggregated": 0,
            "orderbook_processed": 0,
            "errors": 0
        }

    async def initialize(self) -> None:
        """初始化"""
        logger.info("Initializing Aggregation Service...")

        self.publisher = await get_kafka_publisher()
        self.writer = await get_clickhouse_writer()

        await self.writer.create_table()

        self._running = True
        logger.info("Aggregation Service initialized successfully")

    async def shutdown(self) -> None:
        """关闭"""
        logger.info("Shutting down Aggregation Service...")

        closed_candles = self.timeframe_aggregator.close_all()
        for candle in closed_candles:
            await self.publisher.publish_candle(candle)
            await self.writer.insert_candle(candle)

        if self.publisher:
            await self.publisher.shutdown()
        if self.writer:
            await self.writer.shutdown()

        self._running = False
        logger.info(f"Aggregation Service stopped. Stats: {self._stats}")

    async def process_candle(self, candle_data: Dict[str, Any]) -> list[Candle]:
        """处理 K线"""
        try:
            candle = Candle.from_dict(candle_data)

            results = self.timeframe_aggregator.process(candle)

            for aggregated in results:
                await self.publisher.publish_candle(aggregated)
                await self.writer.insert_candle(aggregated)

            self._stats["candles_processed"] += 1
            self._stats["candles_aggregated"] += len(results)

            return results

        except Exception as e:
            logger.error(f"Error processing candle: {e}")
            self._stats["errors"] += 1
            return []

    async def process_trade(self, trade_data: Dict[str, Any]) -> Optional[Candle]:
        """处理成交"""
        try:
            trade = Trade.from_dict(trade_data)

            candle = self.trade_aggregator.process_trade(trade)

            if candle:
                await self.publisher.publish_candle(candle)
                await self.writer.insert_candle(candle)
                self._stats["trades_aggregated"] += 1

            self._stats["trades_processed"] += 1
            return candle

        except Exception as e:
            logger.error(f"Error processing trade: {e}")
            self._stats["errors"] += 1
            return None

    async def process_orderbook(self, snapshot_data: Dict[str, Any]) -> None:
        """处理订单簿"""
        try:
            bids = [OrderBookLevel(p, q) for p, q in snapshot_data.get("bids", [])[:20]]
            asks = [OrderBookLevel(p, q) for p, q in snapshot_data.get("asks", [])[:20]]

            snapshot = OrderBookSnapshot(
                exchange=snapshot_data["exchange"],
                symbol=snapshot_data["symbol"],
                timestamp=snapshot_data["timestamp"],
                bids=bids,
                asks=asks,
                last_update_id=snapshot_data.get("last_update_id", 0)
            )

            feature = self.orderbook_aggregator.process_snapshot(snapshot)
            await self.publisher.publish_orderbook_feature(feature)

            self._stats["orderbook_processed"] += 1

        except Exception as e:
            logger.error(f"Error processing orderbook: {e}")
            self._stats["errors"] += 1

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            **self._stats
        }


_service: Optional[AggregationService] = None


async def get_aggregation_service() -> AggregationService:
    """获取聚合服务"""
    global _service
    if _service is None:
        _service = AggregationService()
        await _service.initialize()
    return _service


async def main():
    service = await get_aggregation_service()

    try:
        state_manager = get_system_state_manager()
        await state_manager.update({"status": "RUNNING"})
        logger.info("Aggregation Service is running. Press Ctrl+C to stop.")

        while service._running:
            await asyncio.sleep(60)

            logger.info(f"Stats: {service.stats}")

    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        await service.shutdown()
        await state_manager.update({"status": "STOPPED"})


if __name__ == "__main__":
    asyncio.run(main())
