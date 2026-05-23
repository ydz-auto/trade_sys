"""
统一数据管道 - 数据采集到消费的完整管道

提供：
- 统一的数据源接口
- 统一的发布接口（带熔断、降级、重试）
- 统一的消费接口（带熔断、降级、重试）
- 统一的监控指标

架构：
DataSource → UnifiedPublisher → Kafka → UnifiedConsumer → Processing
    │              │                         │
    │         熔断器                      熔断器
    │         降级                       降级
    │         重试                       重试
    │         监控                       监控
    ↓              ↓                         ↓
统一格式: StandardEvent ──────────────────────────→ Processing

边界说明：
    unified_pipeline = 数据采集管道 (source → Kafka → consumer)
        职责：数据源接入、消息发布、消息消费、熔断/降级/重试
        不负责：特征计算、时间因果保证、特征矩阵管理

    feature_matrix_runtime = 特征计算运行时 (时间因果保证)
        职责：时间因果一致的特征计算、Label 物理隔离、Point-in-Time 存储
        不负责：数据源接入、消息发布/消费

    两者互补，不重叠：
    - unified_pipeline 负责把数据从源头搬运到消费端
    - feature_matrix_runtime 负责对消费到的数据做时间因果一致的特征计算
    - consumer 的 message_handler 不应直接做特征计算，应委托给 feature_matrix_runtime
"""

import asyncio
from typing import Optional, Dict, Any, List, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod
import json

from infrastructure.logging import get_logger
from infrastructure.resilience import (
    CircuitBreaker,
    CircuitBreakerConfig,
    RetryPolicy,
    RetryConfig
)
from infrastructure.messaging import Topics
from infrastructure.config.defaults.infrastructure.middleware import KAFKA_BOOTSTRAP_SERVERS

logger = get_logger("unified_pipeline")


class DataSourceType(Enum):
    """数据源类型"""
    RSS = "rss"
    API = "api"
    SKILL = "skill"
    WEBSOCKET = "websocket"
    SCRAPER = "scraper"


class PipelineStatus(Enum):
    """管道状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CIRCUIT_OPEN = "circuit_open"
    DOWN = "down"


@dataclass
class PipelineConfig:
    """管道配置"""
    name: str
    source_type: DataSourceType
    kafka_topic: str

    circuit_failure_threshold: int = 3
    circuit_recovery_timeout: float = 60.0

    retry_max_attempts: int = 3
    retry_initial_delay: float = 1.0

    fallback_enabled: bool = True
    fallback_data: Optional[List[Dict]] = None

    batch_size: int = 10
    batch_timeout: float = 5.0

    consumer_group: str = "default_group"
    max_poll_records: int = 100


@dataclass
class PipelineMetrics:
    """管道指标"""
    published_count: int = 0
    consumed_count: int = 0
    failed_count: int = 0
    circuit_open_count: int = 0
    fallback_count: int = 0
    retry_count: int = 0
    last_success_time: Optional[datetime] = None
    last_failure_time: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "published": self.published_count,
            "consumed": self.consumed_count,
            "failed": self.failed_count,
            "circuit_open": self.circuit_open_count,
            "fallback": self.fallback_count,
            "retry": self.retry_count,
            "last_success": self.last_success_time.isoformat() if self.last_success_time else None,
            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None
        }


class UnifiedPublisher:
    """
    统一发布者

    特性：
    - 熔断保护
    - 自动降级
    - 重试机制
    - 批量发布
    - 监控指标
    """

    def __init__(
        self,
        config: PipelineConfig,
        kafka_bootstrap_servers: str = None
    ):
        self.config = config
        self.kafka_servers = kafka_bootstrap_servers or KAFKA_BOOTSTRAP_SERVERS
        self.metrics = PipelineMetrics()

        self.circuit_breaker = CircuitBreaker(
            CircuitBreakerConfig(
                name=f"publisher_{config.name}",
                failure_threshold=config.circuit_failure_threshold,
                recovery_timeout=config.circuit_recovery_timeout
            )
        )

        self.retry_policy = RetryPolicy(
            RetryConfig(
                max_attempts=config.retry_max_attempts,
                initial_delay=config.retry_initial_delay
            )
        )

        self._producer = None
        self._pending_messages: List[Dict] = []
        self._batch_task: Optional[asyncio.Task] = None

        logger.info(f"UnifiedPublisher '{config.name}' initialized")

    async def start(self) -> None:
        """启动发布者"""
        try:
            from aiokafka import AIOKafkaProducer

            self._producer = AIOKafkaProducer(
                bootstrap_servers=self.kafka_servers,
                value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode()
            )
            await self._producer.start()

            self._batch_task = asyncio.create_task(self._batch_publisher())

            logger.info(f"UnifiedPublisher '{self.config.name}' started")
        except Exception as e:
            logger.error(f"Failed to start publisher: {e}")
            raise

    async def stop(self) -> None:
        """停止发布者"""
        if self._batch_task:
            self._batch_task.cancel()
            try:
                await self._batch_task
            except asyncio.CancelledError:
                pass

        if self._producer:
            await self._producer.stop()

        logger.info(f"UnifiedPublisher '{self.config.name}' stopped")

    async def publish(self, event: Dict[str, Any]) -> bool:
        """
        发布单个事件

        Args:
            event: 要发布的事件

        Returns:
            bool: 是否发布成功
        """
        try:
            if not self.circuit_breaker.can_execute():
                self.metrics.circuit_open_count += 1
                logger.warning(f"Circuit breaker open for '{self.config.name}'")

                if self.config.fallback_enabled:
                    return await self._use_fallback()
                return False

            async def _do_publish():
                return await self._send_to_kafka(event)

            result = await self.retry_policy.execute(_do_publish)

            if result:
                self.metrics.published_count += 1
                self.metrics.last_success_time = datetime.now()
                self.circuit_breaker.record_success()
                return True
            else:
                raise Exception("Publish failed")

        except Exception as e:
            self.metrics.failed_count += 1
            self.metrics.last_failure_time = datetime.now()
            self.circuit_breaker.record_failure()
            logger.error(f"Failed to publish event: {e}")

            if self.config.fallback_enabled:
                return await self._use_fallback()
            return False

    async def publish_batch(self, events: List[Dict[str, Any]]) -> int:
        """
        批量发布事件

        Args:
            events: 要发布的事件列表

        Returns:
            int: 成功发布的数量
        """
        success_count = 0
        for event in events:
            if await self.publish(event):
                success_count += 1
        return success_count

    async def _send_to_kafka(self, event: Dict[str, Any]) -> bool:
        """发送消息到 Kafka"""
        if not self._producer:
            raise Exception("Producer not started")

        try:
            key = event.get("id", "").encode() if event.get("id") else None
            await self._producer.send_and_wait(
                self.config.kafka_topic,
                value=event,
                key=key
            )
            return True
        except Exception as e:
            logger.error(f"Kafka send error: {e}")
            raise

    async def _use_fallback(self) -> bool:
        """使用降级数据"""
        self.metrics.fallback_count += 1
        logger.info(f"Using fallback data for '{self.config.name}'")

        if self.config.fallback_data:
            for event in self.config.fallback_data:
                logger.info(f"Fallback event: {event.get('title', 'N/A')[:50]}")
        return True

    async def _batch_publisher(self) -> None:
        """批量发布任务"""
        while True:
            try:
                await asyncio.sleep(self.config.batch_timeout)

                if self._pending_messages and self._producer:
                    events = self._pending_messages[:self.config.batch_size]
                    self._pending_messages = self._pending_messages[self.config.batch_size:]

                    for event in events:
                        try:
                            await self._send_to_kafka(event)
                            self.metrics.published_count += 1
                        except Exception as e:
                            self.metrics.failed_count += 1
                            logger.error(f"Batch send error: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Batch publisher error: {e}")

    def get_metrics(self) -> PipelineMetrics:
        """获取指标"""
        return self.metrics


class DataSource(ABC):
    """数据源抽象基类"""

    @abstractmethod
    async def fetch(self) -> List[Dict[str, Any]]:
        """获取数据"""
        pass

    @abstractmethod
    def get_source_name(self) -> str:
        """获取数据源名称"""
        pass


class UnifiedConsumer:
    """
    统一消费者

    特性：
    - 熔断保护
    - 自动降级
    - 重试机制
    - 消息处理
    - 监控指标

    边界：consumer 只负责消息消费和容错，不负责业务路由。
    message_handler 由调用方传入，consumer 不决定消息去向。
    """

    def __init__(
        self,
        config: PipelineConfig,
        kafka_bootstrap_servers: str = None,
        message_handler: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None
    ):
        self.config = config
        self.kafka_servers = kafka_bootstrap_servers or KAFKA_BOOTSTRAP_SERVERS
        self.message_handler = message_handler
        self.metrics = PipelineMetrics()

        self.circuit_breaker = CircuitBreaker(
            CircuitBreakerConfig(
                name=f"consumer_{config.name}",
                failure_threshold=config.circuit_failure_threshold,
                recovery_timeout=config.circuit_recovery_timeout
            )
        )

        self.retry_policy = RetryPolicy(
            RetryConfig(
                max_attempts=config.retry_max_attempts,
                initial_delay=config.retry_initial_delay
            )
        )

        self._consumer = None
        self._running = False

        logger.info(f"UnifiedConsumer '{config.name}' initialized")

    async def start(self) -> None:
        """启动消费者"""
        try:
            from aiokafka import AIOKafkaConsumer

            self._consumer = AIOKafkaConsumer(
                self.config.kafka_topic,
                bootstrap_servers=self.kafka_servers,
                group_id=self.config.consumer_group,
                value_deserializer=lambda m: json.loads(m.decode())
            )
            await self._consumer.start()
            self._running = True

            logger.info(f"UnifiedConsumer '{self.config.name}' started")

        except Exception as e:
            logger.error(f"Failed to start consumer: {e}")
            raise

    async def stop(self) -> None:
        """停止消费者"""
        self._running = False
        if self._consumer:
            await self._consumer.stop()
        logger.info(f"UnifiedConsumer '{self.config.name}' stopped")

    async def consume(self) -> None:
        """消费消息"""
        if not self._running or not self._consumer:
            raise Exception("Consumer not started")

        try:
            async for message in self._consumer:
                if not self._running:
                    break

                try:
                    await self._process_message(message.value)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    self.metrics.failed_count += 1
        except Exception as e:
            logger.error(f"Consumer error: {e}")

    async def _process_message(self, message: Dict[str, Any]) -> None:
        """处理单条消息"""
        if not self.circuit_breaker.can_execute():
            self.metrics.circuit_open_count += 1
            logger.warning(f"Circuit breaker open for consumer '{self.config.name}'")

            if self.config.fallback_enabled:
                await self._use_fallback_handler(message)
            return

        async def _do_process():
            if self.message_handler:
                await self.message_handler(message)
            return True

        try:
            result = await self.retry_policy.execute(_do_process)

            if result:
                self.metrics.consumed_count += 1
                self.metrics.last_success_time = datetime.now()
                self.circuit_breaker.record_success()
            else:
                raise Exception("Processing failed")

        except Exception as e:
            self.metrics.failed_count += 1
            self.metrics.last_failure_time = datetime.now()
            self.circuit_breaker.record_failure()
            logger.error(f"Failed to process message: {e}")

            if self.config.fallback_enabled:
                await self._use_fallback_handler(message)

    async def _use_fallback_handler(self, message: Dict[str, Any]) -> None:
        """使用降级处理器"""
        self.metrics.fallback_count += 1
        logger.info(f"Using fallback handler for message: {message.get('id', 'N/A')}")

        logger.warning(f"Message processed with fallback: {json.dumps(message, ensure_ascii=False)[:100]}")

    def get_metrics(self) -> PipelineMetrics:
        """获取指标"""
        return self.metrics


class DataPipeline:
    """
    统一数据管道 (Infrastructure 层原语)

    只提供 start/stop/fetch_one_cycle 原语。
    事件循环编排（while running 循环）由 runtime 层负责。

    边界：pipeline 只负责 source → Kafka → consumer 的数据搬运。
    consumer 的 message_handler 由调用方传入，pipeline 不决定业务路由。
    """

    def __init__(
        self,
        config: PipelineConfig,
        data_source: DataSource,
        kafka_bootstrap_servers: str = None,
        message_handler: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None
    ):
        self.config = config
        self.data_source = data_source
        self.publisher = UnifiedPublisher(config, kafka_bootstrap_servers or KAFKA_BOOTSTRAP_SERVERS)
        self.consumer = UnifiedConsumer(config, kafka_bootstrap_servers or KAFKA_BOOTSTRAP_SERVERS, message_handler)

        logger.info(f"DataPipeline '{config.name}' initialized")

    async def start(self) -> None:
        await self.publisher.start()
        await self.consumer.start()
        logger.info(f"DataPipeline '{self.config.name}' started")

    async def stop(self) -> None:
        await self.publisher.stop()
        await self.consumer.stop()
        logger.info(f"DataPipeline '{self.config.name}' stopped")

    async def fetch_and_publish(self) -> int:
        """执行一次 fetch → publish 周期，返回发布的条目数"""
        data = await self.data_source.fetch()
        logger.info(f"Fetched {len(data)} items from {self.data_source.get_source_name()}")
        published = await self.publisher.publish_batch(data)
        logger.info(f"Published {published} items to {self.config.kafka_topic}")
        return published

    def get_status(self) -> PipelineStatus:
        if self.publisher.metrics.failed_count > 10:
            return PipelineStatus.CIRCUIT_OPEN
        elif self.publisher.metrics.failed_count > 5:
            return PipelineStatus.DEGRADED
        return PipelineStatus.HEALTHY

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "status": self.get_status().value,
            "publisher": self.publisher.get_metrics().to_dict(),
            "consumer": self.consumer.get_metrics().to_dict()
        }


def create_rss_pipeline(
    name: str,
    rss_url: str,
    kafka_topic: str,
    kafka_servers: str = None
) -> DataPipeline:
    """创建 RSS 数据管道"""

    class RSSDataSource(DataSource):
        def __init__(self, url: str):
            self.url = url

        async def fetch(self) -> List[Dict[str, Any]]:
            import feedparser
            import httpx

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.url)
                feed = feedparser.parse(response.text)

                items = []
                for entry in feed.entries[:20]:
                    items.append({
                        "id": entry.get("id", ""),
                        "title": entry.get("title", ""),
                        "content": entry.get("summary", "")[:500],
                        "url": entry.get("link", ""),
                        "published": entry.get("published", ""),
                        "source": self.url
                    })
                return items

        def get_source_name(self) -> str:
            return self.url

    config = PipelineConfig(
        name=name,
        source_type=DataSourceType.RSS,
        kafka_topic=kafka_topic
    )

    return DataPipeline(
        config=config,
        data_source=RSSDataSource(rss_url),
        kafka_bootstrap_servers=kafka_servers
    )


def create_skill_pipeline(
    name: str,
    skill_adapter_class,
    kafka_topic: str,
    kafka_servers: str = None,
    **adapter_kwargs
) -> DataPipeline:
    """创建 Skill 数据管道"""

    class SkillDataSource(DataSource):
        def __init__(self, adapter_class, kwargs):
            self.adapter = adapter_class(**kwargs)

        async def fetch(self) -> List[Dict[str, Any]]:
            raw_data = await self.adapter.fetch_raw_data()
            events = self.adapter.normalize(raw_data)
            return [event.to_dict() if hasattr(event, 'to_dict') else event for event in events]

        def get_source_name(self) -> str:
            return self.adapter.__class__.__name__

    config = PipelineConfig(
        name=name,
        source_type=DataSourceType.SKILL,
        kafka_topic=kafka_topic
    )

    return DataPipeline(
        config=config,
        data_source=SkillDataSource(skill_adapter_class, adapter_kwargs),
        kafka_bootstrap_servers=kafka_servers
    )
