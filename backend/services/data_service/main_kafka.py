"""
Data Service - Kafka Producer

发送模拟原始数据到 Kafka

用法:
    python -m services.data_service.main_kafka
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime
import json

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from infrastructure.messaging import get_broker, Topics
from infrastructure.messaging.schema import RawData


SAMPLE_NEWS = [
    {
        "title": "BlackRock's Bitcoin ETF sees $520M daily inflow - largest since launch",
        "content": "Major institutional buying detected",
        "source": "coindesk"
    },
    {
        "title": "Bitcoin institutional adoption accelerates as Fidelity files for new crypto ETF",
        "content": "Bullish sentiment",
        "source": "bloomberg"
    },
    {
        "title": "On-chain data shows large BTC outflows from exchanges - potential accumulation",
        "content": "Whale activity",
        "source": "glassnode"
    },
    {
        "title": "Major Ethereum hack: attacker drains $60M from DeFi protocol",
        "content": "Security breach",
        "source": "theblock"
    },
    {
        "title": "Circle's USDC stablecoin briefly depegs during market volatility",
        "content": "Stablecoin concern",
        "source": "coindesk"
    },
]


async def publish_raw_data(broker, news_item: dict, interval: float = 2.0):
    """发布一条原始数据到 Kafka"""
    raw_data = RawData(
        type="news",
        symbol="BTC",
        source=news_item["source"],
        data=news_item,
    )

    await broker.publish(
        message=raw_data.model_dump(),
        topic=Topics.RAW_DATA,
        key=news_item.get("symbol", "BTC"),
    )

    print(f"[data_service] Published: {news_item['title'][:50]}...")
    return True


async def wait_for_kafka(broker, max_retries=30, delay=2):
    """等待 Kafka 就绪"""
    print(f"\n[data_service] Waiting for Kafka to be ready (max {max_retries} retries)...")
    for i in range(max_retries):
        try:
            await broker.start()
            print(f"[data_service] Kafka is ready!")
            return True
        except Exception as e:
            print(f"[data_service] Attempt {i+1}/{max_retries}: Kafka not ready - {e}")
            await asyncio.sleep(delay)
    return False


async def main():
    print("=" * 60)
    print("Data Service - Kafka Producer")
    print("=" * 60)
    bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    print(f"Broker: {bootstrap_servers}")
    print(f"Topic: {Topics.RAW_DATA}")
    print("=" * 60)

    broker = get_broker(bootstrap_servers)

    if not await wait_for_kafka(broker):
        print("[data_service] Failed to connect to Kafka after retries")
        return

    try:
        print("\nPublishing sample news data...\n")

        for i, news in enumerate(SAMPLE_NEWS, 1):
            try:
                await publish_raw_data(broker, news)
                if i < len(SAMPLE_NEWS):
                    await asyncio.sleep(2)
            except Exception as e:
                print(f"[data_service] Error publishing: {e}")

        print("\n[data_service] Published all sample data")
    finally:
        await broker.stop()


if __name__ == "__main__":
    asyncio.run(main())