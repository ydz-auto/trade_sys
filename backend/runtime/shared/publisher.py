"""
Runtime Publisher - 统一的 Kafka 发布者

所有 Runtime 共享的 Kafka 发布组件。
"""

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

from infrastructure.logging import get_logger
from infrastructure.messaging.kafka_config import DEFAULT_PRODUCER_CONFIG

try:
    from aiokafka import AIOKafkaProducer
    from aiokafka.errors import KafkaError
    AIOKAFKA_AVAILABLE = True
except ImportError:
    AIOKAFKA_AVAILABLE = False
    KafkaError = Exception
    AIOKafkaProducer = None


@dataclass
class PublisherConfig:
    """发布者配置"""
    bootstrap_servers: str
    topic: str
    acks: str = DEFAULT_PRODUCER_CONFIG.acks
    retries: int = DEFAULT_PRODUCER_CONFIG.retries
    max_batch_size: int = DEFAULT_PRODUCER_CONFIG.batch_size
    linger_ms: int = DEFAULT_PRODUCER_CONFIG.linger_ms
    compression_type: str = DEFAULT_PRODUCER_CONFIG.compression_type
    retry_delay_ms: int = 500


class RuntimePublisher:
    """
    统一的 Runtime Kafka 发布者
    
    职责：
    - Kafka 连接管理
    - 消息发布
    - 重试机制
    - 批量发送
    """
    
    def __init__(self, config: PublisherConfig):
        if not AIOKAFKA_AVAILABLE:
            raise RuntimeError("aiokafka not installed. Run: pip install aiokafka")
        
        self.config = config
        self.logger = get_logger(f"publisher.{config.topic}")
        
        self._producer: Optional[AIOKafkaProducer] = None
        self._running = False
        self._batch: list = []
    
    async def start(self) -> None:
        """启动发布者"""
        for attempt in range(self.config.retries):
            try:
                self._producer = AIOKafkaProducer(
                    bootstrap_servers=self.config.bootstrap_servers,
                    acks=self.config.acks,
                    max_batch_size=self.config.max_batch_size,
                    linger_ms=self.config.linger_ms,
                    compression_type=self.config.compression_type,
                    value_serializer=lambda m: json.dumps(m).encode("utf-8"),
                    key_serializer=lambda k: k.encode("utf-8") if k else None,
                )
                
                await self._producer.start()
                
                self._running = True
                self.logger.info(f"Publisher started: {self.config.topic}")
                return
                
            except Exception as e:
                self.logger.warning(f"Start attempt {attempt + 1} failed: {e}")
                if attempt < self.config.retries - 1:
                    await asyncio.sleep(self.config.retry_delay_ms / 1000)
        
        raise RuntimeError(f"Failed to start publisher after {self.config.retries} attempts")
    
    async def stop(self) -> None:
        """停止发布者"""
        self._running = False
        
        if self._batch:
            await self._flush_batch()
        
        if self._producer:
            await self._producer.stop()
            self._producer = None
        
        self.logger.info("Publisher stopped")
    
    async def publish(
        self,
        message: Dict[str, Any],
        key: str = None,
        headers: Dict[str, str] = None,
    ) -> bool:
        """发布消息"""
        if not self._running or not self._producer:
            return False
        
        for attempt in range(self.config.retries):
            try:
                await self._producer.send_and_wait(
                    topic=self.config.topic,
                    value=message,
                    key=key,
                )
                return True
                
            except Exception as e:
                self.logger.warning(f"Publish attempt {attempt + 1} failed: {e}")
                if attempt < self.config.retries - 1:
                    await asyncio.sleep(self.config.retry_delay_ms / 1000 * (attempt + 1))
        
        self.logger.error(f"Failed to publish after {self.config.retries} attempts")
        return False
    
    async def publish_batch(
        self,
        messages: list,
        key: str = None,
    ) -> int:
        """批量发布消息"""
        success_count = 0
        for message in messages:
            if await self.publish(message, key):
                success_count += 1
        return success_count
    
    async def _flush_batch(self) -> None:
        """刷新批量消息"""
        if not self._batch:
            return
        
        batch = self._batch.copy()
        self._batch.clear()
        
        for message in batch:
            await self.publish(message)
    
    async def is_healthy(self) -> bool:
        """检查健康状态"""
        return self._running and self._producer is not None
