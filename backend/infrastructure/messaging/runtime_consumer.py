"""
Runtime Consumer - 统一的 Kafka 消费者

所有 Runtime 共享的 Kafka 消费组件。
使用简单模式，避免复杂的消费者组协调器问题
"""

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Union

from infrastructure.logging import get_logger
from infrastructure.messaging.kafka_config import DEFAULT_CONSUMER_CONFIG
from infrastructure.messaging.schema.base_event import BaseEvent

try:
    from aiokafka import AIOKafkaConsumer
    from aiokafka.errors import KafkaError
    AIOKAFKA_AVAILABLE = True
except ImportError:
    AIOKAFKA_AVAILABLE = False
    KafkaError = Exception
    AIOKafkaConsumer = None


@dataclass
class ConsumerConfig:
    """消费者配置"""
    bootstrap_servers: str
    topics: List[str]
    group_id: str
    auto_offset_reset: str = "latest"
    enable_auto_commit: bool = DEFAULT_CONSUMER_CONFIG.enable_auto_commit
    max_poll_records: int = DEFAULT_CONSUMER_CONFIG.max_poll_records
    session_timeout_ms: int = DEFAULT_CONSUMER_CONFIG.session_timeout_ms
    heartbeat_interval_ms: int = DEFAULT_CONSUMER_CONFIG.heartbeat_interval_ms
    max_poll_interval_ms: int = DEFAULT_CONSUMER_CONFIG.max_poll_interval_ms
    request_timeout_ms: int = DEFAULT_CONSUMER_CONFIG.request_timeout_ms
    retry_attempts: int = DEFAULT_CONSUMER_CONFIG.retry_attempts
    retry_delay_ms: int = DEFAULT_CONSUMER_CONFIG.retry_delay_ms


class RuntimeConsumer:
    """
    统一的 Runtime Kafka 消费者
    
    使用简单的subscribe模式，配置更长的超时时间
    
    职责：
    - Kafka 连接管理
    - 消息消费
    - 重试机制
    - 错误处理
    """
    
    def __init__(self, config: ConsumerConfig):
        if not AIOKAFKA_AVAILABLE:
            raise RuntimeError("aiokafka not installed. Run: pip install aiokafka")
        
        self.config = config
        self.logger = get_logger(f"consumer.{config.group_id}")
        
        self._consumer: Optional[AIOKafkaConsumer] = None
        self._running = False
        self._handlers: Dict[str, Callable] = {}
    
    def register_handler(self, topic: str, handler: Callable) -> None:
        """注册消息处理器"""
        self._handlers[topic] = handler
    
    async def start(self) -> None:
        """启动消费者"""
        for attempt in range(self.config.retry_attempts):
            try:
                self.logger.info(f"Starting consumer (attempt {attempt + 1}/{self.config.retry_attempts})...")
                self.logger.info(f"Bootstrap servers: {self.config.bootstrap_servers}")
                self.logger.info(f"Topics: {self.config.topics}")
                
                self._consumer = AIOKafkaConsumer(
                    *self.config.topics,
                    bootstrap_servers=self.config.bootstrap_servers,
                    group_id=self.config.group_id,
                    auto_offset_reset=self.config.auto_offset_reset,
                    enable_auto_commit=self.config.enable_auto_commit,
                    session_timeout_ms=self.config.session_timeout_ms,
                    heartbeat_interval_ms=self.config.heartbeat_interval_ms,
                    max_poll_interval_ms=self.config.max_poll_interval_ms,
                    request_timeout_ms=self.config.request_timeout_ms,
                    max_poll_records=self.config.max_poll_records,
                    value_deserializer=lambda m: json.loads(m.decode("utf-8")) if m else None,
                    key_deserializer=lambda m: m.decode("utf-8") if m else None,
                )
                
                await self._consumer.start()
                
                self._running = True
                self.logger.info(f"✅ Consumer started successfully: {self.config.topics}")
                return
                
            except Exception as e:
                self.logger.error(f"❌ Start attempt {attempt + 1} failed: {e}")
                if self._consumer:
                    try:
                        await self._consumer.stop()
                    except:
                        pass
                    self._consumer = None
                
                if attempt < self.config.retry_attempts - 1:
                    self.logger.info(f"Retrying in {self.config.retry_delay_ms / 1000} seconds...")
                    await asyncio.sleep(self.config.retry_delay_ms / 1000)
        
        raise RuntimeError(f"Failed to start consumer after {self.config.retry_attempts} attempts")
    
    async def stop(self) -> None:
        """停止消费者"""
        self._running = False
        
        if self._consumer:
            await self._consumer.stop()
            self._consumer = None
        
        self.logger.info("Consumer stopped")
    
    async def consume(self, timeout: float = 1.0) -> Optional[Dict[str, Any]]:
        if not self._running or not self._consumer:
            return None

        try:
            import asyncio as aio
            result = await aio.wait_for(
                self._consumer.getone(),
                timeout=timeout
            )

            if result:
                self.logger.info(f"Consumed message from {result.topic}:{result.partition}:{result.offset}")
                return {
                    "topic": result.topic,
                    "partition": result.partition,
                    "offset": result.offset,
                    "key": result.key,
                    "value": result.value,
                    "timestamp": result.timestamp,
                }
            return None
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            self.logger.error(f"Consume error: {e}")
            return None

    async def consume_event(self, timeout: float = 1.0) -> Optional[BaseEvent]:
        if not self._running or not self._consumer:
            return None

        try:
            import asyncio as aio
            result = await aio.wait_for(
                self._consumer.getone(),
                timeout=timeout,
            )

            if result and result.value:
                from infrastructure.messaging.event_registry import parse_event
                from infrastructure.messaging.serializer import EventSerializer
                value = result.value
                if isinstance(value, dict):
                    return parse_event(value)
                if isinstance(value, str):
                    import json as _json
                    return parse_event(_json.loads(value))
                if isinstance(value, bytes):
                    return EventSerializer.deserialize(value)
                return None
            return None
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            self.logger.error(f"consume_event error: {e}")
            return None
    
    async def run(self) -> None:
        """运行消费循环"""
        while self._running:
            try:
                message = await self.consume(timeout=1.0)
                if message:
                    await self._dispatch(message)
            except Exception as e:
                self.logger.error(f"Error in consume loop: {e}")
                await asyncio.sleep(1.0)
    
    async def _dispatch(self, message: Dict[str, Any]) -> None:
        """分发消息到处理器"""
        topic = message.get("topic", "")
        handler = self._handlers.get(topic)
        
        if handler:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as e:
                self.logger.error(f"Handler error for {topic}: {e}")
    
    async def is_healthy(self) -> bool:
        """检查健康状态"""
        return self._running and self._consumer is not None
