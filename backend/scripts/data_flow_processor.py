#!/usr/bin/env python3
"""
自动数据流处理器 - 从Kafka读取数据并写入Redis
替代有问题的Projection Runtime Consumer
"""
import asyncio
import json
import sys
import os
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from aiokafka import AIOKafkaConsumer
    from infrastructure.cache.redis_client import init_redis, get_redis_client
    from services.projection_service.state_keys import ProjectionKeys
    from infrastructure.logging import get_logger
    logger = get_logger('data_flow_processor')
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)


class DataFlowProcessor:
    """数据流处理器"""
    
    def __init__(self):
        self.redis = None
        self.consumer = None
        self.running = False
        
    async def initialize(self):
        """初始化"""
        logger.info("Initializing data flow processor...")
        
        # 连接Redis
        self.redis = await init_redis()
        logger.info("✅ Redis connected")
        
        # 创建Kafka消费者 - 使用简化的配置
        bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        logger.info(f"Connecting to Kafka: {bootstrap_servers}")
        
        self.consumer = AIOKafkaConsumer(
            'tradeagent.events',
            bootstrap_servers=bootstrap_servers,
            group_id='data_flow_processor',
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            session_timeout_ms=60000,
            heartbeat_interval_ms=10000,
            max_poll_interval_ms=600000,
            api_version='auto',
            value_deserializer=lambda m: json.loads(m.decode('utf-8')) if m else None,
            key_deserializer=lambda m: m.decode('utf-8') if m else None,
        )
        
        await self.consumer.start()
        logger.info("✅ Kafka consumer started")
        
    async def process_messages(self):
        """处理消息"""
        logger.info("Starting message processing...")
        self.running = True
        
        news_list = []
        processed_count = 0
        
        try:
            async for message in self.consumer:
                if not self.running:
                    break
                    
                try:
                    if message.value:
                        event = message.value
                        event_type = event.get('event_type')
                        
                        if event_type == 'news':
                            news_data = event.get('data', {})
                            news_item = {
                                'id': news_data.get('id', ''),
                                'title': news_data.get('title', ''),
                                'content': news_data.get('content', ''),
                                'source': news_data.get('source', ''),
                                'url': news_data.get('url', ''),
                                'published': news_data.get('published', 0),
                                'sentiment': news_data.get('sentiment', 'neutral'),
                                'sentiment_score': news_data.get('sentiment_score', 0.5),
                            }
                            news_list.append(news_item)
                            logger.info(f"📰 Processed news: {news_item['title'][:50]}...")
                            
                        processed_count += 1
                        
                        # 每处理10条消息就更新一次Redis
                        if processed_count % 10 == 0 and news_list:
                            await self.update_redis(news_list)
                            logger.info(f"💾 Updated Redis with {len(news_list)} news items")
                            
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Consumer error: {e}")
        finally:
            # 最后一次更新
            if news_list:
                await self.update_redis(news_list)
                
    async def update_redis(self, news_list):
        """更新Redis"""
        try:
            # 读取现有状态
            existing_state = await self.redis.get_json(ProjectionKeys.dashboard_state()) or {}
            
            # 更新新闻列表
            existing_state['news'] = news_list[-20:]  # 只保留最新的20条
            existing_state['last_update'] = datetime.utcnow().isoformat()
            existing_state['source'] = 'data_flow_processor'
            
            # 写入Redis
            await self.redis.set_json(ProjectionKeys.dashboard_state(), existing_state)
            
        except Exception as e:
            logger.error(f"Error updating Redis: {e}")
            
    async def run(self):
        """运行处理器"""
        try:
            await self.initialize()
            await self.process_messages()
        except Exception as e:
            logger.error(f"Processor error: {e}")
        finally:
            await self.shutdown()
            
    async def shutdown(self):
        """关闭"""
        logger.info("Shutting down...")
        self.running = False
        
        if self.consumer:
            await self.consumer.stop()
            
        logger.info("✅ Shutdown complete")


async def main():
    """主函数"""
    processor = DataFlowProcessor()
    
    try:
        await processor.run()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
        await processor.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
