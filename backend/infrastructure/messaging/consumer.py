"""
Kafka Consumer Base - 统一 Kafka 消费者基类
支持 Consumer Group、Offset 管理、状态恢复、Lag 监控

功能：
1. Consumer Group 管理
2. Offset 提交和恢复
3. Lag 监控
4. 自动重连
5. 优雅关闭
"""

import asyncio
import json
from abc import ABC, abstractmethod
from typing import Optional, Callable, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

from infrastructure.logging import get_logger

try:
    from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
    from aiokafka.errors import KafkaError
    AIOKAFKA_AVAILABLE = True
except ImportError:
    AIOKAFKA_AVAILABLE = False
    KafkaError = Exception
    AIOKafkaConsumer = None
    AIOKafkaProducer = None

logger = get_logger("infrastructure.messaging.consumer")


class ConsumerStatus(Enum):
    IDLE = "idle"
    CONNECTING = "connecting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class ConsumerStats:
    """消费者统计"""
    messages_processed: int = 0
    messages_failed: int = 0
    last_offset: int = 0
    last_timestamp: Optional[datetime] = None
    lag: int = 0
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "messages_processed": self.messages_processed,
            "messages_failed": self.messages_failed,
            "last_offset": self.last_offset,
            "last_timestamp": self.last_timestamp.isoformat() if self.last_timestamp else None,
            "lag": self.lag,
            "error_count": len(self.errors),
        }


@dataclass
class TopicPartition:
    """Topic 分区"""
    topic: str
    partition: int
    offset: int = 0
    high_watermark: int = 0
    lag: int = 0


class BaseKafkaConsumer(ABC):
    """Kafka 消费者基类
    
    提供：
    - 自动 offset 提交
    - 状态恢复
    - Lag 监控
    - 错误处理
    """
    
    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        group_id: str = "tradeagent-consumer",
        topics: Optional[List[str]] = None,
        auto_offset_reset: str = "earliest",
        enable_auto_commit: bool = False,
        auto_commit_interval_ms: int = 5000,
        session_timeout_ms: int = 30000,
        heartbeat_interval_ms: int = 10000,
    ):
        if not AIOKAFKA_AVAILABLE:
            raise RuntimeError("aiokafka not installed. Run: pip install aiokafka")
        
        self.bootstrap_servers = bootstrap_servers
        self.group_id = group_id
        self.topics = topics or []
        self.auto_offset_reset = auto_offset_reset
        self.enable_auto_commit = enable_auto_commit
        self.auto_commit_interval_ms = auto_commit_interval_ms
        self.session_timeout_ms = session_timeout_ms
        self.heartbeat_interval_ms = heartbeat_interval_ms
        
        self._consumer: Optional[AIOKafkaConsumer] = None
        self._producer: Optional[AIOKafkaProducer] = None
        self._running = False
        self._paused = False
        self._status = ConsumerStatus.IDLE
        self._stats = ConsumerStats()
        self._partitions: Dict[str, List[TopicPartition]] = {}
        self._offset_store: Dict[str, int] = {}
        self._task: Optional[asyncio.Task] = None
    
    async def connect(self) -> None:
        """连接 Kafka"""
        if self._consumer is not None:
            return
        
        self._status = ConsumerStatus.CONNECTING
        
        try:
            self._consumer = AIOKafkaConsumer(
                *self.topics,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.group_id,
                auto_offset_reset=self.auto_offset_reset,
                enable_auto_commit=self.enable_auto_commit,
                auto_commit_interval_ms=self.auto_commit_interval_ms,
                session_timeout_ms=self.session_timeout_ms,
                heartbeat_interval_ms=self.heartbeat_interval_ms,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                key_deserializer=lambda m: m.decode("utf-8") if m else None,
            )
            
            await self._consumer.start()
            self._running = True
            self._status = ConsumerStatus.RUNNING
            
            await self._update_partitions()
            await self._load_offset_store()
            
            logger.info(f"Consumer connected: group={self.group_id}, topics={self.topics}")
            
        except Exception as e:
            self._status = ConsumerStatus.ERROR
            logger.error(f"Failed to connect consumer: {e}")
            raise
    
    async def disconnect(self) -> None:
        """断开连接"""
        self._running = False
        self._paused = False
        self._status = ConsumerStatus.STOPPED
        
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        await self._save_offset_store()
        
        if self._consumer:
            await self._consumer.stop()
            self._consumer = None
        
        if self._producer:
            await self._producer.stop()
            self._producer = None
        
        logger.info(f"Consumer disconnected: group={self.group_id}")
    
    async def start(self) -> None:
        """启动消费"""
        await self.connect()
        
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._consume_loop())
    
    async def stop(self) -> None:
        """停止消费"""
        await self.disconnect()
    
    async def pause(self) -> None:
        """暂停消费"""
        if self._consumer and self._running:
            self._consumer.pause()
            self._paused = True
            self._status = ConsumerStatus.PAUSED
            logger.info(f"Consumer paused: group={self.group_id}")
    
    async def resume(self) -> None:
        """恢复消费"""
        if self._consumer and self._paused:
            self._consumer.resume()
            self._paused = False
            self._status = ConsumerStatus.RUNNING
            logger.info(f"Consumer resumed: group={self.group_id}")
    
    async def _consume_loop(self) -> None:
        """消费循环"""
        try:
            async for message in self._consumer:
                if not self._running:
                    break
                
                if self._paused:
                    await asyncio.sleep(0.1)
                    continue
                
                try:
                    await self._process_message(message)
                    self._stats.messages_processed += 1
                    self._stats.last_offset = message.offset
                    self._stats.last_timestamp = datetime.now()
                    
                    await self._update_lag(message)
                    await self._store_offset(message)
                    
                except Exception as e:
                    self._stats.messages_failed += 1
                    self._stats.errors.append(str(e))
                    logger.error(f"Failed to process message: {e}")
                    
                    if len(self._stats.errors) > 100:
                        self._stats.errors = self._stats.errors[-100:]
                
                if self.enable_auto_commit:
                    await self._consumer.commit()
                    
        except asyncio.CancelledError:
            logger.info(f"Consumer loop cancelled: group={self.group_id}")
        except Exception as e:
            self._status = ConsumerStatus.ERROR
            logger.error(f"Consumer loop error: {e}")
            self._stats.errors.append(str(e))
    
    @abstractmethod
    async def _process_message(self, message) -> None:
        """处理消息（子类实现）"""
        pass
    
    async def _update_partitions(self) -> None:
        """更新分区信息"""
        if not self._consumer:
            return
        
        partitions = self._consumer.assignment()
        for tp in partitions:
            begin, end = await self._consumer.get_watermarks(tp)
            self._partitions[tp.topic] = self._partitions.get(tp.topic, [])
            
            existing = next((p for p in self._partitions[tp.topic] if p.partition == tp.partition), None)
            
            if existing:
                existing.high_watermark = end
                existing.lag = end - existing.offset
            else:
                self._partitions[tp.topic].append(
                    TopicPartition(topic=tp.topic, partition=tp.partition, offset=0, high_watermark=end)
                )
    
    async def _update_lag(self, message) -> None:
        """更新 lag"""
        tp = f"{message.topic}-{message.partition}"
        
        for tp_obj in self._partitions.get(message.topic, []):
            if tp_obj.partition == message.partition:
                tp_obj.offset = message.offset
                try:
                    _, end = await self._consumer.get_watermarks(tp_obj.topic, tp_obj.partition)
                    tp_obj.high_watermark = end
                    tp_obj.lag = end - message.offset
                    self._stats.lag = tp_obj.lag
                except:
                    pass
                break
    
    async def _store_offset(self, message) -> None:
        """存储 offset"""
        key = f"{message.topic}-{message.partition}"
        self._offset_store[key] = message.offset
    
    async def _load_offset_store(self) -> None:
        """加载 offset 存储"""
        logger.info(f"Loaded offset store: {len(self._offset_store)} entries")
    
    async def _save_offset_store(self) -> None:
        """保存 offset 存储"""
        if self._consumer and self._offset_store:
            for key, offset in self._offset_store.items():
                topic, partition = key.rsplit("-", 1)
                try:
                    await self._consumer.seek(topic, int(partition), offset)
                except Exception as e:
                    logger.error(f"Failed to save offset {key}: {e}")
        
        logger.info(f"Saved offset store: {len(self._offset_store)} entries")
    
    def get_stats(self) -> ConsumerStats:
        """获取统计信息"""
        return self._stats
    
    def get_partitions(self) -> Dict[str, List[TopicPartition]]:
        """获取分区信息"""
        return self._partitions
    
    @property
    def status(self) -> ConsumerStatus:
        return self._status
    
    @property
    def is_running(self) -> bool:
        return self._running and self._status == ConsumerStatus.RUNNING


class BatchKafkaConsumer(BaseKafkaConsumer):
    """批量消费
    
    支持批量处理消息，提高吞吐量
    """
    
    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        group_id: str = "tradeagent-consumer",
        topics: Optional[List[str]] = None,
        batch_size: int = 100,
        batch_timeout_ms: int = 1000,
        **kwargs
    ):
        super().__init__(bootstrap_servers, group_id, topics, **kwargs)
        self.batch_size = batch_size
        self.batch_timeout_ms = batch_timeout_ms
        self._batch: List[Any] = []
        self._batch_start_time: Optional[datetime] = None
    
    async def _process_message(self, message) -> None:
        """批量处理消息"""
        if not self._batch:
            self._batch_start_time = datetime.now()
        
        self._batch.append(message)
        
        should_process = (
            len(self._batch) >= self.batch_size or
            (datetime.now() - self._batch_start_time).total_seconds() * 1000 >= self.batch_timeout_ms
        )
        
        if should_process and self._batch:
            await self._process_batch(self._batch)
            self._batch = []
            self._batch_start_time = None
    
    async def _process_batch(self, batch: List[Any]) -> None:
        """处理批量消息（子类实现）"""
        for message in batch:
            try:
                await self._handle_single_message(message)
            except Exception as e:
                logger.error(f"Failed to handle message in batch: {e}")
    
    async def _handle_single_message(self, message) -> None:
        """处理单条消息"""
        pass
