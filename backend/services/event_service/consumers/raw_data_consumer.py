"""
Kafka Consumer - 消费原始数据，转换为事件
"""

import asyncio
import json
from typing import Optional, Callable, Awaitable
from datetime import datetime

from infrastructure.logging import get_logger
from infrastructure.config.defaults.infrastructure.middleware import KAFKA_BOOTSTRAP_SERVERS
logger = get_logger("event_service.consumer")

try:
    from faststream import FastStream
    from faststream.kafka import KafkaBroker, KafkaMessage
    from faststream.kafka.annotations import KafkaBroker as KafkaBrokerAnnot
    FASTSTREAM_AVAILABLE = True
except ImportError:
    FASTSTREAM_AVAILABLE = False
    logger.warning("FastStream not available")


class RawDataConsumer:
    def __init__(
        self,
        bootstrap_servers: Optional[str] = None,
        event_handler: Optional[Callable] = None
    ):
        self.bootstrap_servers = bootstrap_servers or KAFKA_BOOTSTRAP_SERVERS
        self._broker: Optional[KafkaBroker] = None
        self._app: Optional[FastStream] = None
        self._event_handler = event_handler
        self._running = False

    def set_event_handler(self, handler: Callable) -> None:
        self._event_handler = handler

    async def connect(self) -> None:
        if not FASTSTREAM_AVAILABLE:
            logger.warning("FastStream not available")
            return

        try:
            self._broker = KafkaBroker(self.bootstrap_servers)
            self._app = FastStream(self._broker, title="TradeAgent Event Service", version="1.0.0")
            self._running = True
            logger.info("Raw data consumer connected to Kafka")
        except Exception as e:
            logger.error(f"Failed to connect Kafka consumer: {e}")
            self._running = False

    async def disconnect(self) -> None:
        self._running = False
        if self._app:
            await self._app.stop()
        logger.info("Raw data consumer disconnected")

    async def start_consuming(self) -> None:
        if not self._running or not self._broker:
            logger.warning("Consumer not connected")
            return

        logger.info("Starting to consume from tradeagent.raw_data topic")

    @property
    def is_running(self) -> bool:
        return self._running


_raw_data_consumer: Optional[RawDataConsumer] = None


def get_raw_data_consumer(
    bootstrap_servers: Optional[str] = None,
    event_handler: Optional[Callable] = None
) -> RawDataConsumer:
    global _raw_data_consumer
    if _raw_data_consumer is None:
        _raw_data_consumer = RawDataConsumer(bootstrap_servers or KAFKA_BOOTSTRAP_SERVERS, event_handler)
    return _raw_data_consumer


class RawDataMessageParser:
    @staticmethod
    def parse_news(raw: dict) -> Optional[dict]:
        if raw.get("data_type") == "news" or "title" in raw.get("data", {}):
            data = raw.get("data", raw)
            return {
                "message_id": raw.get("message_id", raw.get("id", "")),
                "data_type": "news",
                "source": data.get("source", "unknown"),
                "title": data.get("title", ""),
                "content": data.get("content", ""),
                "url": data.get("url", ""),
                "raw_content": data.get("title", "") + " " + data.get("content", ""),
                "timestamp": data.get("published", data.get("timestamp", datetime.now().timestamp())),
                "collected_at": datetime.now().timestamp(),
                "metadata": {
                    "sentiment": data.get("sentiment"),
                    "sentiment_score": data.get("sentiment_score"),
                    "black_swan": data.get("black_swan"),
                    "entities": data.get("entities", []),
                    "topics": data.get("topics", []),
                }
            }
        return None

    @staticmethod
    def parse_social(raw: dict) -> Optional[dict]:
        if raw.get("data_type") == "social" or "platform" in raw.get("data", {}):
            data = raw.get("data", raw)
            return {
                "message_id": raw.get("message_id", raw.get("id", "")),
                "data_type": "social",
                "source": data.get("platform", "unknown"),
                "content": data.get("content", ""),
                "raw_content": data.get("content", ""),
                "title": "",
                "timestamp": data.get("published", data.get("timestamp", datetime.now().timestamp())),
                "collected_at": datetime.now().timestamp(),
                "metadata": {
                    "author": data.get("author", ""),
                    "platform": data.get("platform", ""),
                    "url": data.get("url", ""),
                    "likes": data.get("likes", 0),
                    "retweets": data.get("retweets", 0),
                }
            }
        return None

    @staticmethod
    def parse_trader_opinion(raw: dict) -> Optional[dict]:
        if raw.get("data_type") == "trader_opinion" or "trader" in raw.get("data", {}):
            data = raw.get("data", raw)
            return {
                "message_id": raw.get("message_id", raw.get("id", "")),
                "data_type": "trader_opinion",
                "source": data.get("platform", data.get("trader", "unknown")),
                "content": data.get("content", data.get("opinion", "")),
                "raw_content": data.get("content", data.get("opinion", "")),
                "title": "",
                "timestamp": data.get("posted_at", data.get("timestamp", datetime.now().timestamp())),
                "collected_at": datetime.now().timestamp(),
                "metadata": {
                    "trader_name": data.get("trader", ""),
                    "asset": data.get("asset", "BTC"),
                    "platform": data.get("platform", "twitter"),
                    "sentiment": data.get("sentiment"),
                    "confidence": data.get("confidence", 0.5),
                }
            }
        return None

    @staticmethod
    def parse_etf_flow(raw: dict) -> Optional[dict]:
        if raw.get("data_type") == "etf_flow" or "net_flow" in raw.get("data", {}):
            data = raw.get("data", raw)
            return {
                "message_id": raw.get("message_id", raw.get("id", "")),
                "data_type": "etf_flow",
                "source": "etf",
                "content": data,
                "raw_content": f"ETF {data.get('symbol', 'BTC')}: net_flow={data.get('net_flow', 0)}",
                "title": "",
                "timestamp": data.get("timestamp", datetime.now().timestamp()),
                "collected_at": datetime.now().timestamp(),
                "metadata": {
                    "symbol": data.get("symbol", "BTC"),
                    "net_flow": data.get("net_flow", 0),
                    "inflow": data.get("inflow", 0),
                    "outflow": data.get("outflow", 0),
                    "aum": data.get("aum", 0),
                }
            }
        return None

    @staticmethod
    def parse_onchain(raw: dict) -> Optional[dict]:
        if raw.get("data_type") == "onchain" or "wallet_address" in raw.get("data", {}):
            data = raw.get("data", raw)
            return {
                "message_id": raw.get("message_id", raw.get("id", "")),
                "data_type": "onchain",
                "source": data.get("source", "dune"),
                "content": data,
                "raw_content": f"Wallet {data.get('wallet_address', '')}: net_flow={data.get('net_flow', 0)}",
                "title": "",
                "timestamp": data.get("last_active", data.get("timestamp", datetime.now().timestamp())),
                "collected_at": datetime.now().timestamp(),
                "metadata": {
                    "wallet_address": data.get("wallet_address", ""),
                    "label": data.get("label", ""),
                    "net_flow": data.get("net_flow", 0),
                    "balance": data.get("balance", 0),
                }
            }
        return None

    @classmethod
    def parse_message(cls, raw: dict) -> Optional[dict]:
        parsers = [
            cls.parse_news,
            cls.parse_social,
            cls.parse_trader_opinion,
            cls.parse_etf_flow,
            cls.parse_onchain,
        ]

        for parser in parsers:
            try:
                result = parser(raw)
                if result:
                    return result
            except Exception as e:
                logger.debug(f"Parser {parser.__name__} failed: {e}")
                continue

        logger.warning(f"No parser matched for message: {raw.get('message_id', 'unknown')}")
        return None
