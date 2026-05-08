"""
Data Service - Kafka Producer

从真实数据源采集数据并发送到 Kafka

用法:
    python -m services.data_service.main_kafka
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from infrastructure.messaging import get_broker, Topics
from infrastructure.messaging.schema import RawData
from services.data_service.collectors.news_collector import NewsCollector


async def publish_raw_data(broker, news_item: dict, interval: float = 2.0):
    """发布一条原始数据到 Kafka"""
    raw_data = RawData(
        type="news",
        symbol=news_item.get("affected_symbols", ["BTC"])[0] if news_item.get("affected_symbols") else "BTC",
        source=news_item["source"],
        data=news_item,
    )

    await broker.publish(
        message=raw_data.model_dump(),
        topic=Topics.RAW_DATA,
        key=news_item.get("affected_symbols", ["BTC"])[0] if news_item.get("affected_symbols") else "BTC",
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
    print("Data Service - Kafka Producer (Real Data)")
    print("=" * 60)
    bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    print(f"Broker: {bootstrap_servers}")
    print(f"Topic: {Topics.RAW_DATA}")
    print("=" * 60)

    broker = get_broker(bootstrap_servers)

    if not await wait_for_kafka(broker):
        print("[data_service] Failed to connect to Kafka after retries")
        return

    news_collector = NewsCollector()
    collection_interval = int(os.environ.get("COLLECTION_INTERVAL", "300"))

    try:
        print("\nStarting real-time news collection...\n")
        print("Data sources: coindesk, cointelegraph, cryptopanic, etc.")
        print(f"Collection interval: {collection_interval} seconds")
        print()

        while True:
            try:
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Collecting news from all sources...")
                news_items = await news_collector.collect()

                if news_items:
                    print(f"Collected {len(news_items)} news items")

                    for news in news_items[:10]:
                        await publish_raw_data(broker, news_collector._to_dict(news))

                    print(f"Published {min(10, len(news_items))} news items to Kafka")
                else:
                    print("No news collected, will retry...")

            except Exception as e:
                print(f"[data_service] Collection error: {e}")

            await asyncio.sleep(collection_interval)

    except KeyboardInterrupt:
        print("\n[data_service] Shutting down...")
    finally:
        await broker.stop()


if __name__ == "__main__":
    asyncio.run(main())
