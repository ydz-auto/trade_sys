"""
Runtime Bus - Runtime 统一通信总线

核心职责:
1. 所有 runtime 统一通信
2. 替代分散的 redis/ws/service call
3. 支持同步/异步消息
"""
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import asyncio

from domain.trading_mode import TradingMode, get_trading_mode_manager
from runtime.isolation import get_runtime_isolation
from infrastructure.logging import get_logger

logger = get_logger("runtime.bus")


class MessageType(str, Enum):
    EVENT = "event"
    COMMAND = "command"
    QUERY = "query"
    BROADCAST = "broadcast"


@dataclass
class BusMessage:
    message_id: str
    message_type: MessageType
    topic: str
    payload: Any
    source: Optional[str] = None
    target: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class RuntimeBus:
    _instance: Optional['RuntimeBus'] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._initialized = True
        
        self._mode_manager = get_trading_mode_manager()
        self._isolation = get_runtime_isolation()
        
        self._subscribers: Dict[str, List[Callable]] = {}
        self._queues: Dict[str, asyncio.Queue] = {}
        
        self._message_history: List[BusMessage] = []
        self._max_history = 1000
        
        self._message_counter = 0
        
        self._stats = {
            "total_published": 0,
            "total_consumed": 0,
            "by_topic": {},
        }
        
        self._backtest_states: Dict[str, Any] = {}
        
        logger.info("RuntimeBus initialized")

    def _generate_message_id(self) -> str:
        self._message_counter += 1
        return f"msg_{self._message_counter}"

    def _get_namespaced_topic(self, topic: str) -> str:
        namespace = self._isolation.get_namespace()
        return f"{namespace}.{topic}"

    def subscribe(
        self,
        topic: str,
        handler: Callable,
        use_namespace: bool = True,
    ) -> str:
        full_topic = self._get_namespaced_topic(topic) if use_namespace else topic
        
        if full_topic not in self._subscribers:
            self._subscribers[full_topic] = []
        
        self._subscribers[full_topic].append(handler)
        
        if full_topic not in self._queues:
            self._queues[full_topic] = asyncio.Queue(maxsize=10000)
        
        logger.info(f"Subscribed to topic: {full_topic}")
        
        return full_topic

    def unsubscribe(self, topic: str, handler: Callable) -> None:
        if topic in self._subscribers:
            self._subscribers[topic] = [
                h for h in self._subscribers[topic] if h != handler
            ]

    async def publish(
        self,
        topic: str,
        payload: Any,
        message_type: MessageType = MessageType.EVENT,
        source: Optional[str] = None,
        use_namespace: bool = True,
    ) -> str:
        full_topic = self._get_namespaced_topic(topic) if use_namespace else topic
        
        message = BusMessage(
            message_id=self._generate_message_id(),
            message_type=message_type,
            topic=full_topic,
            payload=payload,
            source=source,
        )
        
        self._message_history.append(message)
        if len(self._message_history) > self._max_history:
            self._message_history = self._message_history[-self._max_history:]
        
        self._stats["total_published"] += 1
        self._stats["by_topic"][full_topic] = self._stats["by_topic"].get(full_topic, 0) + 1
        
        if full_topic in self._queues:
            try:
                self._queues[full_topic].put_nowait(message)
            except asyncio.QueueFull:
                logger.warning(f"Queue full for topic: {full_topic}")
        
        handlers = self._subscribers.get(full_topic, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
                self._stats["total_consumed"] += 1
            except Exception as e:
                logger.error(f"Handler error for {full_topic}: {e}")
        
        return message.message_id

    async def publish_event(
        self,
        event_type: str,
        data: Dict[str, Any],
        source: Optional[str] = None,
    ) -> str:
        return await self.publish(
            topic=f"event.{event_type}",
            payload=data,
            message_type=MessageType.EVENT,
            source=source,
        )

    async def publish_command(
        self,
        command: str,
        target: str,
        params: Dict[str, Any],
        source: Optional[str] = None,
    ) -> str:
        return await self.publish(
            topic=f"command.{command}",
            payload=params,
            message_type=MessageType.COMMAND,
            source=source,
        )

    async def broadcast(
        self,
        topic: str,
        payload: Any,
    ) -> str:
        return await self.publish(
            topic=topic,
            payload=payload,
            message_type=MessageType.BROADCAST,
            use_namespace=False,
        )

    async def get_message(self, topic: str, timeout: float = 1.0) -> Optional[BusMessage]:
        full_topic = self._get_namespaced_topic(topic)
        
        if full_topic not in self._queues:
            return None
        
        try:
            message = await asyncio.wait_for(
                self._queues[full_topic].get(),
                timeout=timeout,
            )
            self._stats["total_consumed"] += 1
            return message
        except asyncio.TimeoutError:
            return None

    def get_history(
        self,
        topic: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        history = self._message_history[-limit:]
        
        if topic:
            full_topic = self._get_namespaced_topic(topic)
            history = [m for m in history if topic in m.topic]
        
        return [
            {
                "message_id": m.message_id,
                "type": m.message_type.value,
                "topic": m.topic,
                "source": m.source,
                "timestamp": m.timestamp.isoformat(),
            }
            for m in history
        ]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "mode": self._mode_manager.mode.value,
            "subscribers": len(self._subscribers),
            "queues": len(self._queues),
            "stats": self._stats.copy(),
        }

    def get_state(self, key: str) -> Optional[Any]:
        return self._backtest_states.get(key)

    def set_state(self, key: str, value: Any) -> None:
        self._backtest_states[key] = value


def get_runtime_bus() -> RuntimeBus:
    return RuntimeBus()


async def publish(topic: str, payload: Any, **kwargs) -> str:
    bus = get_runtime_bus()
    return await bus.publish(topic, payload, **kwargs)


async def publish_event(event_type: str, data: Dict[str, Any], **kwargs) -> str:
    bus = get_runtime_bus()
    return await bus.publish_event(event_type, data, **kwargs)
