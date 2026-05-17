#!/usr/bin/env python3
"""
从Kafka读取真实新闻数据并写入Redis
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from aiokafka import AIOKafkaConsumer
from infrastructure.cache.redis_client import init_redis
from services.projection_service.state_keys import ProjectionKeys
from infrastructure.logging import get_logger
from shared.config.defaults.infrastructure.middleware import KAFKA_BOOTSTRAP_SERVERS

logger = get_logger('kafka_to_redis')


async def main():
    logger.info("Starting Kafka to Redis migration...")
    
    # 连接Redis
    redis = await init_redis()
    logger.info("Redis connected")
    
    # 创建Kafka消费者
    consumer = AIOKafkaConsumer(
        'tradeagent.events',
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id='real_data_writer',
        auto_offset_reset='earliest',
        value_deserializer=lambda m: json.loads(m.decode('utf-8')) if m else None,
        consumer_timeout_ms=10000,
    )
    
    await consumer.start()
    logger.info("Kafka consumer started")
    
    news_list = []
    message_count = 0
    
    try:
        async for message in consumer:
            if message.value:
                event = message.value
                logger.info(f"Received event: {event.get('event_type')}")
                
                if event.get('event_type') == 'news':
                    news_data = event.get('data', {})
                    news_list.append({
                        'id': news_data.get('id', ''),
                        'title': news_data.get('title', ''),
                        'content': news_data.get('content', ''),
                        'source': news_data.get('source', ''),
                        'url': news_data.get('url', ''),
                        'published': news_data.get('published', 0),
                        'sentiment': news_data.get('sentiment', 'neutral'),
                        'sentiment_score': news_data.get('sentiment_score', 0.5),
                    })
                    message_count += 1
                    logger.info(f"Collected news: {news_data.get('title', 'No title')}")
                    
                    if message_count >= 20:
                        break
    except Exception as e:
        logger.error(f"Error consuming messages: {e}")
    finally:
        await consumer.stop()
    
    logger.info(f"Total news collected: {len(news_list)}")
    
    if news_list:
        # 构建dashboard状态
        dashboard_state = {
            'prices': {},
            'factors': {},
            'regime': {},
            'signals': {},
            'news': news_list,
            'compositeScore': 0.5,
            'last_update': None,
            'source': 'kafka_real_data',
        }
        
        # 写入Redis
        await redis.set_json(
            ProjectionKeys.dashboard_state(),
            dashboard_state
        )
        
        logger.info(f"✅ Wrote {len(news_list)} real news items to Redis")
        logger.info(f"Dashboard state key: {ProjectionKeys.dashboard_state()}")
        
        # 打印前3条新闻标题
        for i, news in enumerate(news_list[:3], 1):
            logger.info(f"  {i}. {news['title']}")
    else:
        logger.warning("❌ No news data found in Kafka")
        logger.info("Please check if Ingestion Runtime is running and publishing to Kafka")


if __name__ == "__main__":
    asyncio.run(main())
