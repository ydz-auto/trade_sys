"""
Kafka Queue - FastStream 实现
"""

from typing import Optional
from infrastructure.logging import get_logger

logger = get_logger("data_service.queue")

try:
    from infrastructure.middleware.kafka import (
        get_kafka_broker,
        get_kafka_publisher,
        KafkaPublisher,
        KafkaBroker,
        init_kafka,
        close_kafka,
    )
    FASTSTREAM_AVAILABLE = True
except ImportError:
    FASTSTREAM_AVAILABLE = False
    logger.warning("FastStream not available, Kafka will be disabled")


class KafkaProducerWrapper:
    def __init__(self):
        self._broker: Optional[KafkaBroker] = None
        self._publisher: Optional[KafkaPublisher] = None
        self._connected = False

    async def connect(self) -> None:
        if not FASTSTREAM_AVAILABLE:
            logger.warning("FastStream not available, skipping Kafka connection")
            return
        try:
            from infrastructure.middleware.config import KafkaConfig
            config = KafkaConfig()
            self._broker = get_kafka_broker(config.bootstrap_servers)
            self._publisher = get_kafka_publisher(self._broker)
            self._connected = True
            logger.info("Kafka producer connected (FastStream)")
        except Exception as e:
            logger.error(f"Failed to connect Kafka: {e}")
            self._connected = False

    async def disconnect(self) -> None:
        if FASTSTREAM_AVAILABLE:
            await close_kafka()
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def send(self, topic: str, value: dict, key: Optional[str] = None) -> None:
        if self._publisher:
            await self._publisher.publish(topic, value, key=key)

    async def publish_raw_data(self, data: dict, symbol: str) -> None:
        """Publish raw data to tradeagent.raw_data topic"""
        if self._publisher:
            await self._publisher.publish("tradeagent.raw_data", data, key=symbol)

    async def publish_features(self, data: dict, symbol: str) -> None:
        """Publish features to tradeagent.features topic"""
        if self._publisher:
            await self._publisher.publish("tradeagent.features", data, key=symbol)

    async def publish_factors(self, data: dict, symbol: str) -> None:
        """Publish factors to tradeagent.factors topic"""
        if self._publisher:
            await self._publisher.publish("tradeagent.factors", data, key=symbol)

    async def publish_signals(self, data: dict, symbol: str) -> None:
        """Publish signals to tradeagent.signals topic"""
        if self._publisher:
            await self._publisher.publish("tradeagent.signals", data, key=symbol)

    async def publish_order_event(self, data: dict, order_id: str) -> None:
        """Publish order events to tradeagent.orders topic"""
        if self._publisher:
            await self._publisher.publish("tradeagent.orders", data, key=order_id)


kafka_producer = KafkaProducerWrapper()

__all__ = ["kafka_producer", "KafkaProducerWrapper"]
