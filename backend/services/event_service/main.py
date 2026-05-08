"""
Event Service - 主入口
负责将原始数据转换为结构化事件

数据流:
  tradeagent.raw_data (Kafka) -> EventService -> tradeagent.events (Kafka)

LLM只在这里被调用！
"""

import asyncio
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any
from datetime import datetime
import json

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from infrastructure.logging import get_logger
logger = get_logger("event_service.main")

from shared.config import get_datasource_config_manager
from shared.state import get_system_state_manager

from .services import EventExtractor, get_event_extractor
from .producers import EventProducer, get_event_producer
from .consumers import RawDataConsumer, RawDataMessageParser, get_raw_data_consumer
from .schemas import RawDataMessage, RawDataType, Event, EventType

SERVICE_NAME = "event_service"


class EventService:
    def __init__(self):
        self.extractor: Optional[EventExtractor] = None
        self.producer: Optional[EventProducer] = None
        self.consumer: Optional[RawDataConsumer] = None
        self._running = False
        self._processed_count = 0
        self._error_count = 0

    async def initialize(self) -> None:
        logger.info("Initializing Event Service...")

        self.extractor = get_event_extractor()
        self.producer = get_event_producer()
        self.consumer = get_raw_data_consumer()

        await self.producer.connect()
        await self.consumer.connect()

        self._running = True
        logger.info("Event Service initialized successfully")

    async def shutdown(self) -> None:
        logger.info("Shutting down Event Service...")
        self._running = False

        if self.producer:
            await self.producer.disconnect()
        if self.consumer:
            await self.consumer.disconnect()

        logger.info(f"Event Service stopped. Processed: {self._processed_count}, Errors: {self._error_count}")

    async def process_raw_message(self, raw_message: Dict[str, Any]) -> Optional[Event]:
        try:
            parsed = RawDataMessageParser.parse_message(raw_message)
            if not parsed:
                logger.debug(f"Could not parse message: {raw_message.get('message_id', 'unknown')}")
                return None

            raw_data_msg = RawDataMessage(**parsed)

            event = await self.extractor.extract_from_raw_data(raw_data_msg)

            event_dict = event.model_dump()
            key = f"{event.event_type.value}:{event.asset}"

            success = await self.producer.publish_event(event_dict, key=key)

            if success:
                self._processed_count += 1
                logger.debug(f"Processed event: {event.event_id} -> {event.event_type.value}")
            else:
                logger.warning(f"Failed to publish event: {event.event_id}")

            return event

        except Exception as e:
            self._error_count += 1
            logger.error(f"Error processing raw message: {e}")
            return None

    async def process_batch(self, messages: List[Dict[str, Any]]) -> List[Event]:
        events = []
        for msg in messages:
            event = await self.process_raw_message(msg)
            if event:
                events.append(event)
        return events

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "processed_count": self._processed_count,
            "error_count": self._error_count,
            "cache_size": len(self.extractor._cache) if self.extractor else 0,
        }


event_service: Optional[EventService] = None


async def get_event_service() -> EventService:
    global event_service
    if event_service is None:
        event_service = EventService()
        await event_service.initialize()
    return event_service


async def main():
    service = await get_event_service()

    try:
        state_manager = get_system_state_manager()
        await state_manager.update({"status": "RUNNING"})
        logger.info("Event Service is running. Press Ctrl+C to stop.")

        while service._running:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        await service.shutdown()
        await state_manager.update({"status": "STOPPED"})


if __name__ == "__main__":
    asyncio.run(main())
