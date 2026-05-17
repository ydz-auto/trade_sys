#!/usr/bin/env python3
"""
定期从Kafka读取数据并写入Redis
绕过Consumer协调器问题
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

logger = get_logger('kafka_to_redis_periodic')


async def main():
    logger.info("Starting periodic Kafka to Redis migration...")
    
    redis = await init_redis()
    logger.info("Redis connected")
    
    while True:
        try:
            consumer = AIOKafkaConsumer(
                'tradeagent.events',
                bootstrap_servers='kafka:29092',
                group_id=f'periodic_writer_{int(asyncio.get_event_loop().time())}',
                auto_offset_reset='earliest',
                value_deserializer=lambda m: json.loads(m.decode('utf-8')) if m else None,
                consumer_timeout_ms=5000,
            )
            
            await consumer.start()
            logger.info("Kafka consumer started")
            
            news_list = []
            message_count = 0
            
            async for message in consumer:
                if message.value:
                    event = message.value
                    
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
                        
                        if message_count >= 50:
                            break
            
            await consumer.stop()
            
            if news_list:
                dashboard_state = {
                    'prices': {},
                    'factors': {},
                    'regime': {},
                    'signals': {},
                    'news': news_list,
                    'compositeScore': 0.5,
                    'last_update': None,
                    'source': 'kafka_periodic',
                }
                
                await redis.set_json(
                    ProjectionKeys.dashboard_state(),
                    dashboard_state
                )
                
                logger.info(f"✅ Wrote {len(news_list)} news items to Redis")
            else:
                logger.info("No new news data")
            
            logger.info("Sleeping for 60 seconds...")
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(f"Error: {e}")
            await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(main())
