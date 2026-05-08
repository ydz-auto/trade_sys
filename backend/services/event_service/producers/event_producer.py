"""
Kafka Producer - 事件发布到 Kafka
"""

from typing import Optional, Dict, Any
from dataclasses import asdict
import json

from infrastructure.logging import get_logger
logger = get_logger("event_service.producer")

try:
    from infrastructure.middleware.kafka import (
        get_kafka_broker,
        get_kafka_publisher,
        KafkaPublisher,
        KafkaBroker,
    )
    FASTSTREAM_AVAILABLE = True
except ImportError:
    FASTSTREAM_AVAILABLE = False
    logger.warning("FastStream not available")


class EventProducer:
    def __init__(self):
        self._broker: Optional[KafkaBroker] = None
        self._publisher: Optional[KafkaPublisher] = None
        self._connected = False

    async def connect(self, bootstrap_servers: str = "localhost:9092") -> None:
        if not FASTSTREAM_AVAILABLE:
            logger.warning("FastStream not available, Kafka will be disabled")
            return

        try:
            self._broker = get_kafka_broker(bootstrap_servers)
            self._publisher = get_kafka_publisher(self._broker)
            self._connected = True
            logger.info("Event producer connected to Kafka")
        except Exception as e:
            logger.error(f"Failed to connect Kafka: {e}")
            self._connected = False

    async def disconnect(self) -> None:
        self._connected = False
        logger.info("Event producer disconnected")

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def publish_event(self, event_dict: Dict[str, Any], key: Optional[str] = None) -> bool:
        if not self._connected or not self._publisher:
            logger.warning("Publisher not connected, event dropped")
            return False

        try:
            topic = "tradeagent.events"
            await self._publisher.publish(topic, event_dict, key=key or event_dict.get("asset", "BTC"))
            logger.debug(f"Published event {event_dict.get('event_id')} to {topic}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish event: {e}")
            return False

    async def publish_event_batch(self, events: list, keys: Optional[list] = None) -> int:
        success_count = 0
        for i, event in enumerate(events):
            key = keys[i] if keys and i < len(keys) else None
            if await self.publish_event(event, key):
                success_count += 1
        return success_count


_event_producer: Optional[EventProducer] = None


def get_event_producer() -> EventProducer:
    global _event_producer
    if _event_producer is None:
        _event_producer = EventProducer()
    return _event_producer
