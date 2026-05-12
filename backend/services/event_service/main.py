"""
Event Service - 主入口
负责将原始数据转换为结构化事件

数据流:
  raw.* (Kafka) → EventService → events.* (Kafka)

架构：
data_service (事实层)
    ↓
event_service (理解层)
    ├── understanding/
    │   ├── skills/      # Skill 适配器（ODaily, Twitter, Macro, ETF）
    │   ├── parser/      # 原始数据解析
    │   ├── extractor/  # 事件提取（LLM）
    │   ├── classifier/  # 事件分类
    │   ├── engine/      # 理解引擎
    │   └── hub/         # 理解中心
    ↓
fusion_service (共识层)
"""

import asyncio
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from infrastructure.logging import get_logger
logger = get_logger("event_service.main")

from shared.config import get_datasource_config_manager
from shared.state import get_system_state_manager

from .understanding import (
    UnderstandingHub,
    UnderstandingEngine,
    get_understanding_hub
)
from .understanding.parser import get_data_parser
from .understanding.classifier import get_event_classifier
from .understanding.extractor import get_event_extractor
from .understanding.skills.odaily import get_odaily_collector
from .producers import EventProducer, get_event_producer
from .consumers import RawDataConsumer, RawDataMessageParser, get_raw_data_consumer
from .schemas import RawDataMessage, RawDataType, Event, EventType

SERVICE_NAME = "event_service"


class EventService:
    def __init__(self):
        self.hub: Optional[UnderstandingHub] = None
        self.engine: Optional[UnderstandingEngine] = None
        self.producer: Optional[EventProducer] = None
        self.consumer: Optional[RawDataConsumer] = None
        self._running = False
        self._processed_count = 0
        self._error_count = 0

    async def initialize(self) -> None:
        logger.info("Initializing Event Service...")

        self.hub = await get_understanding_hub()
        self.engine = self.hub.engine

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

            enriched = await self.hub.engine.understand(
                raw_data=raw_data_msg.content,
                source_type=raw_data_msg.data_type.value if hasattr(raw_data_msg.data_type, 'value') else str(raw_data_msg.data_type)
            )

            event = self._create_event_from_enriched(enriched, raw_data_msg)

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

    def _create_event_from_enriched(self, enriched, raw_message: RawDataMessage) -> Event:
        """从增强内容创建事件"""
        extraction = enriched.llm_extraction

        return Event(
            event_id=f"evt_{raw_message.message_id[:8]}",
            event_type=extraction.get("event_type", EventType.SENTIMENT_NARRATIVE_TREND),
            asset=extraction.get("affected_assets", ["BTC"])[0] if extraction.get("affected_assets") else "BTC",
            direction=extraction.get("direction", "neutral"),
            strength=extraction.get("strength", 0.5),
            confidence=extraction.get("confidence", 0.5),
            sources=[raw_message.source],
            source_details=[{"source": raw_message.source, "original": raw_message.content}],
            timestamp=raw_message.timestamp,
            metadata={
                "summary": extraction.get("summary", ""),
                "affected_assets": extraction.get("affected_assets", []),
                "narratives": enriched.narratives,
                "sentiment_score": enriched.sentiment_score,
                "actionability": enriched.actionability,
                **extraction.get("metadata", {})
            },
            raw_data_refs=[raw_message.message_id]
        )

    async def process_batch(self, messages: List[Dict[str, Any]]) -> List[Event]:
        events = []
        for msg in messages:
            event = await self.process_raw_message(msg)
            if event:
                events.append(event)
        return events

    async def get_intelligence_report(self):
        """获取情报报告（通过 Understanding Hub）"""
        if self.hub:
            return await self.hub.get_intelligence_report()
        return None

    async def generate_trading_context(self):
        """生成交易上下文"""
        if self.hub:
            return await self.hub.generate_trading_context()
        return None

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "processed_count": self._processed_count,
            "error_count": self._error_count,
            "cache_size": len(self.engine.extractor._cache) if self.engine and hasattr(self.engine, 'extractor') else 0,
            "regime": self.engine._current_context.regime.value if self.engine and self.engine._current_context else "unknown"
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
