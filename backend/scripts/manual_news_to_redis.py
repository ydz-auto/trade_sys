"""
手动将Kafka中的新闻数据写入Redis
绕过Projection Runtime的Kafka消费者问题
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from aiokafka import AIOKafkaConsumer
from infrastructure.cache.redis_client import init_redis, get_redis_client
from infrastructure.logging import get_logger
from services.projection_service.state_keys import ProjectionKeys

logger = get_logger("manual_news_to_redis")


async def main():
    """主函数"""
    logger.info("Starting manual news to Redis migration...")
    
    redis = await init_redis()
    logger.info("Redis connected")
    
    consumer = AIOKafkaConsumer(
        "tradeagent.events",
        bootstrap_servers="localhost:9092",
        group_id="manual_news_writer",
        auto_offset_reset="earliest",
        value_deserializer=lambda m: json.loads(m.decode("utf-8")) if m else None,
    )
    
    await consumer.start()
    logger.info("Kafka consumer started")
    
    news_list = []
    message_count = 0
    
    try:
        async for message in consumer:
            if message.value:
                event = message.value
                if event.get("event_type") == "news":
                    news_data = event.get("data", {})
                    news_list.append({
                        "id": news_data.get("id", ""),
                        "title": news_data.get("title", ""),
                        "content": news_data.get("content", ""),
                        "source": news_data.get("source", ""),
                        "url": news_data.get("url", ""),
                        "published": news_data.get("published", 0),
                        "sentiment": news_data.get("sentiment", "neutral"),
                        "sentiment_score": news_data.get("sentiment_score", 0.5),
                    })
                    message_count += 1
                    
                    if message_count >= 10:
                        break
    except Exception as e:
        logger.error(f"Error consuming messages: {e}")
    finally:
        await consumer.stop()
    
    if news_list:
        dashboard_state = {
            "prices": {},
            "factors": {},
            "regime": {},
            "signals": {},
            "news": news_list,
            "compositeScore": 0.5,
            "last_update": None,
            "source": "manual_migration",
        }
        
        await redis.set_json(
            ProjectionKeys.dashboard_state(),
            dashboard_state
        )
        
        logger.info(f"Wrote {len(news_list)} news items to Redis")
        logger.info(f"Dashboard state key: {ProjectionKeys.dashboard_state()}")
    else:
        logger.warning("No news data found in Kafka")
    
    logger.info("Migration completed")


if __name__ == "__main__":
    asyncio.run(main())
