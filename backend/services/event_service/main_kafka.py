"""
Event Service - Kafka Consumer + Producer

消费 raw_data，转换为 events，发布到 Kafka

用法:
    python -m services.event_service.main_kafka
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

import os

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from infrastructure.logging import get_logger
logger = get_logger("event_service.kafka")

from infrastructure.messaging import get_broker, Topics
from infrastructure.messaging.schema import RawData, Event
from domain.event import EventType, Direction, get_direction
from services.event_service.mapper import map_event_type


class SimpleEventDetector:
    """简化版事件检测器"""

    EVENT_PATTERNS = {
        "inflow": EventType.FLOW_ETF_INFLOW,
        "outflow": EventType.FLOW_ETF_OUTFLOW,
        "etf": EventType.POLICY_ETF_APPROVAL,
        "hack": EventType.PROTOCOL_HACK,
        "exploit": EventType.PROTOCOL_HACK,
        "depeg": EventType.RISK_STABLECOIN_DEPEG,
        "institutional": EventType.POLICY_REGULATION_POSITIVE,
        "adoption": EventType.POLICY_REGULATION_POSITIVE,
    }

    def detect(self, title: str, content: str) -> Optional[Event]:
        text = (title + " " + content).lower()

        for keyword, event_type in self.EVENT_PATTERNS.items():
            if keyword in text:
                direction = get_direction(event_type)
                strength = 0.7 + (0.3 * hash(title) % 100 / 100)

                asset = "BTC"
                if "eth" in text or "ethereum" in text:
                    asset = "ETH"
                elif "sol" in text or "solana" in text:
                    asset = "SOL"

                return Event(
                    event_type=event_type.value,
                    category=event_type.category.value,
                    source="news",
                    asset=asset,
                    direction=direction.value,
                    strength=min(strength, 1.0),
                    sources=["news"],
                    metadata={"title": title, "source": "coindesk"},
                )

        return None


broker = None
detector = SimpleEventDetector()


async def handle_raw_data(msg: dict):
    """处理原始数据，发布事件"""
    try:
        raw_data = RawData(**msg) if isinstance(msg, dict) else msg

        title = raw_data.data.get("title", "") if isinstance(raw_data.data, dict) else ""
        content = raw_data.data.get("content", "") if isinstance(raw_data.data, dict) else ""

        event = detector.detect(title, content)

        if event:
            event_dict = event.model_dump()
            print(f"[event_service] Detected: {event.event_type} -> {event.asset} ({event.direction})")

            await broker.publish(
                message=event_dict,
                topic=Topics.EVENTS,
                key=event.asset,
            )
            print(f"[event_service] Published to {Topics.EVENTS}")
        else:
            print(f"[event_service] No event detected for: {title[:50]}...")

    except Exception as e:
        print(f"[event_service] Error: {e}")


async def main():
    global broker

    print("=" * 60)
    print("Event Service - Kafka Consumer")
    print("=" * 60)
    bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    print(f"Broker: {bootstrap_servers}")
    print(f"Subscribe: {Topics.RAW_DATA}")
    print(f"Publish: {Topics.EVENTS}")
    print("=" * 60)

    broker = get_broker(bootstrap_servers)

    print("\n[event_service] Starting to consume...\n")

    @broker.subscriber(Topics.RAW_DATA)
    async def on_raw_data(msg: dict):
        await handle_raw_data(msg)

    await broker.run()


if __name__ == "__main__":
    asyncio.run(main())
