"""
Data Worker - 数据采集 + 聚合

合并 data_service + aggregation_service

职责：
1. 从多个数据源采集数据（新闻、行情等）
2. 聚合数据（K线、订单簿、成交）
3. 发布到 Kafka

用法:
    python -m services.workers.data_worker
"""

import asyncio
import sys
import os
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from infrastructure.logging import get_logger
logger = get_logger("workers.data_worker")

from infrastructure.messaging import get_broker, Topics
from infrastructure.messaging.schema import (
    RawDataEvent,
    MarketEvent,
    EventType,
    EventSource,
    generate_trace_id,
)

try:
    from services.data_service.collectors.news_collector import NewsCollector
    NEWS_COLLECTOR_TYPE = "enhanced"
except Exception:
    from services.data_service.collectors.news_collector_simple import NewsCollector
    NEWS_COLLECTOR_TYPE = "simple"

from services.aggregation_service.aggregators.candle.candle_aggregator import get_timeframe_aggregator
from services.aggregation_service.aggregators.trade.trade_aggregator import get_trade_aggregator
from services.aggregation_service.publishers.kafka_publisher import get_kafka_publisher
from services.aggregation_service.publishers.clickhouse_writer import get_clickhouse_writer
from services.aggregation_service.models.candle_model import Candle


class DataWorker:
    """
    数据 Worker
    
    合并 data_service + aggregation_service
    """
    
    def __init__(self):
        self.broker = None
        self.news_collector: Optional[NewsCollector] = None
        self.timeframe_aggregator = get_timeframe_aggregator()
        self.trade_aggregator = get_trade_aggregator()
        self.publisher = None
        self.writer = None
        
        self._running = False
        self._stats = {
            "news_collected": 0,
            "news_published": 0,
            "candles_aggregated": 0,
            "trades_aggregated": 0,
            "errors": 0,
        }
    
    async def initialize(self) -> None:
        """初始化"""
        logger.info("Initializing Data Worker...")
        
        bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        self.broker = get_broker(bootstrap_servers)
        
        try:
            await self.broker.start()
            logger.info(f"Connected to Kafka: {bootstrap_servers}")
        except Exception as e:
            logger.warning(f"Kafka not available: {e}, will retry...")
        
        self.news_collector = NewsCollector()
        logger.info(f"News collector initialized (type={NEWS_COLLECTOR_TYPE})")
        
        try:
            self.publisher = await get_kafka_publisher()
            self.writer = await get_clickhouse_writer()
            await self.writer.create_table()
            logger.info("Aggregation publishers initialized")
        except Exception as e:
            logger.warning(f"Aggregation publishers init failed: {e}")
        
        self._running = True
        logger.info("Data Worker initialized successfully")
    
    async def shutdown(self) -> None:
        """关闭"""
        logger.info("Shutting down Data Worker...")
        self._running = False
        
        if self.broker:
            await self.broker.stop()
        if self.publisher:
            await self.publisher.shutdown()
        if self.writer:
            await self.writer.shutdown()
        
        logger.info(f"Data Worker stopped. Stats: {self._stats}")
    
    async def publish_raw_data(self, news_item: dict, trace_id: str = None) -> bool:
        """发布原始数据到 Kafka"""
        try:
            symbols = news_item.get("affected_symbols", ["BTC"])
            if isinstance(symbols, list) and len(symbols) > 0:
                symbol = symbols[0]
            else:
                symbol = "BTC"
            
            symbol = self._normalize_symbol(symbol)
            
            event = RawDataEvent(
                trace_id=trace_id or generate_trace_id(),
                source=EventSource.DATA_WORKER,
                symbol=symbol,
                data_type="news",
                data=news_item,
                data_source=news_item.get("source", "unknown"),
            )
            
            await self.broker.get_broker().publish(
                event.model_dump(),
                topic=Topics.RAW_DATA,
                key=symbol.encode() if isinstance(symbol, str) else symbol,
            )
            
            self._stats["news_published"] += 1
            logger.debug(f"Published raw data: trace_id={event.trace_id}, symbol={symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Error publishing raw data: {e}")
            self._stats["errors"] += 1
            return False
    
    def _normalize_symbol(self, symbol: str) -> str:
        """标准化交易对格式"""
        if not symbol:
            return "BTCUSDT"
        symbol = symbol.upper()
        if "/" not in symbol and "USDT" not in symbol:
            return f"{symbol}USDT"
        return symbol
    
    async def process_candle(self, candle_data: Dict[str, Any], trace_id: str = None) -> list:
        """处理 K线聚合"""
        try:
            candle = Candle.from_dict(candle_data)
            results = self.timeframe_aggregator.process(candle)
            
            for aggregated in results:
                if self.publisher:
                    await self.publisher.publish_candle(aggregated)
                if self.writer:
                    await self.writer.insert_candle(aggregated)
            
            self._stats["candles_aggregated"] += len(results)
            return results
            
        except Exception as e:
            logger.error(f"Error processing candle: {e}")
            self._stats["errors"] += 1
            return []
    
    async def run_news_collection(self, interval: int = 300) -> None:
        """运行新闻采集循环"""
        logger.info(f"Starting news collection (interval={interval}s)")
        
        while self._running:
            try:
                trace_id = generate_trace_id()
                logger.info(f"[{trace_id}] Collecting news from all sources...")
                
                news_items = await self.news_collector.collect()
                
                if news_items:
                    logger.info(f"[{trace_id}] Collected {len(news_items)} news items")
                    self._stats["news_collected"] += len(news_items)
                    
                    for news in news_items[:10]:
                        await self.publish_raw_data(news.to_dict(), trace_id=trace_id)
                else:
                    logger.debug(f"[{trace_id}] No news collected")
                
            except Exception as e:
                logger.error(f"News collection error: {e}")
                self._stats["errors"] += 1
            
            await asyncio.sleep(interval)
    
    async def run(self) -> None:
        """运行 Worker"""
        await self.initialize()
        
        try:
            collection_interval = int(os.environ.get("COLLECTION_INTERVAL", "300"))
            
            await asyncio.gather(
                self.run_news_collection(collection_interval),
            )
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        finally:
            await self.shutdown()
    
    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            **self._stats
        }


async def main():
    """主入口"""
    print("=" * 60)
    print("Data Worker - News Collection + Aggregation")
    print("=" * 60)
    print(f"News Collector: {NEWS_COLLECTOR_TYPE}")
    print(f"Publish to: {Topics.RAW_DATA}")
    print("=" * 60)
    
    worker = DataWorker()
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
