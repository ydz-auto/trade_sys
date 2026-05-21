"""
Runtime Bus - Runtime 统一通信总线

核心职责:
1. 所有 runtime 统一通信
2. 替代分散的 redis/ws/service call
3. 支持同步/异步消息
4. 兼容原来的 EventBus 功能（迁移到这里
"""
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import json
from pathlib import Path
from collections import defaultdict

from domain.trading_mode import TradingMode, get_trading_mode_manager
from runtime.isolation import get_runtime_isolation
from infrastructure.logging import get_logger

# 兼容原来的 EventBus 导入
try:
    from shared.contracts import StandardEvent, EventFilter, EventType, Source
    EVENT_BUS_AVAILABLE = True
except ImportError:
    EVENT_BUS_AVAILABLE = False

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


@dataclass
class Subscription:
    """订阅配置（兼容 EventBus"""
    id: str
    name: str
    callback: Callable
    filter: Optional[Any] = None  # Optional[EventFilter]
    priority: int = 0


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
        
        # EventBus 兼容属性
        self._event_subscriptions: Dict[str, List[Subscription]] = defaultdict(list)
        self._event_history: List[Any] = []  # List[StandardEvent]
        self._max_event_history = 10000
        self._event_bus_stats = {
            "total_events": 0,
            "published_events": 0,
            "consumed_events": 0,
            "by_type": defaultdict(int),
            "by_source": defaultdict(int)
        }
        
        logger.info("RuntimeBus initialized with EventBus compatibility")

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
            "event_bus_stats": self._event_bus_stats.copy(),
            "event_subscribers": len(self._event_subscriptions.get("all", [])),
        }
    
    # ========================================================================
    # 以下是 EventBus 兼容方法（用于平滑迁移）
    # ========================================================================
    
    def subscribe(
        self,
        name: str,
        callback: Callable,
        filter: Any = None,
        priority: int = 0
    ) -> str:
        """订阅事件（EventBus 兼容接口）"""
        import uuid
        sub_id = str(uuid.uuid4())
        
        subscription = Subscription(
            id=sub_id,
            name=name,
            callback=callback,
            filter=filter,
            priority=priority
        )
        
        self._event_subscriptions["all"].append(subscription)
        
        # 按优先级排序
        self._event_subscriptions["all"].sort(key=lambda s: s.priority, reverse=True)
        
        logger.info(f"Event subscribed: {name} (id={sub_id})")
        return sub_id
    
    def subscribe_by_type(
        self,
        event_type: Any,  # EventType
        name: str,
        callback: Callable,
        filter: Any = None,
        priority: int = 0
    ) -> str:
        """订阅特定类型的事件（EventBus 兼容）"""
        sub_id = self.subscribe(name, callback, filter, priority)
        if EVENT_BUS_AVAILABLE:
            self._event_subscriptions["all"][-1].filter = EventFilter(event_types=[event_type])
        return sub_id
    
    def subscribe_by_source(
        self,
        source: Any,  # Source
        name: str,
        callback: Callable,
        filter: Any = None,
        priority: int = 0
    ) -> str:
        """订阅特定来源的事件（EventBus 兼容）"""
        sub_id = self.subscribe(name, callback, filter, priority)
        if EVENT_BUS_AVAILABLE:
            self._event_subscriptions["all"][-1].filter = EventFilter(sources=[source])
        return sub_id
    
    def unsubscribe(self, sub_id: str):
        """取消订阅（EventBus 兼容）"""
        for subs in self._event_subscriptions.values():
            subs[:] = [s for s in subs if s.id != sub_id]
        logger.info(f"Event unsubscribed: {sub_id}")
    
    async def publish_event(self, event: Any):  # StandardEvent
        """发布事件（EventBus 兼容）"""
        self._event_bus_stats["total_events"] += 1
        if EVENT_BUS_AVAILABLE and hasattr(event, "event_type"):
            self._event_bus_stats["by_type"][event.event_type] += 1
        if EVENT_BUS_AVAILABLE and hasattr(event, "source"):
            self._event_bus_stats["by_source"][event.source] += 1
        
        # 记录历史
        self._event_history.append(event)
        if len(self._event_history) > self._max_event_history:
            self._event_history.pop(0)
        
        # 分发给订阅者
        await self._dispatch_event(event)
        
        self._event_bus_stats["published_events"] += 1
    
    async def publish_events(self, events: List[Any]):
        """批量发布事件（EventBus 兼容）"""
        for event in events:
            await self.publish_event(event)
    
    async def _dispatch_event(self, event: Any):
        """分发事件给订阅者（EventBus 兼容）"""
        tasks = []
        
        for subscription in self._event_subscriptions.get("all", []):
            try:
                # 检查过滤器
                if subscription.filter and hasattr(subscription.filter, "matches"):
                    if not subscription.filter.matches(event):
                        continue
                
                # 异步执行回调
                callback = subscription.callback
                if asyncio.iscoroutinefunction(callback):
                    tasks.append(callback(event))
                else:
                    # 同步函数，在线程池执行
                    loop = asyncio.get_event_loop()
                    tasks.append(loop.run_in_executor(None, callback, event))
                    
            except Exception as e:
                logger.error(f"Error dispatching to {subscription.name}: {e}")
        
        # 等待所有回调完成
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        self._event_bus_stats["consumed_events"] += len(tasks)
    
    def get_event_history(
        self,
        event_type: str = None,
        source: str = None,
        limit: int = 100
    ) -> List[Any]:
        """获取事件历史（EventBus 兼容）"""
        events = self._event_history
        
        if event_type:
            events = [e for e in events if hasattr(e, "event_type") and e.event_type == event_type]
        
        if source:
            events = [e for e in events if hasattr(e, "source") and e.source == source]
        
        return events[-limit:]
    
    def replay_events(self, events: List[Any]):
        """重放事件（EventBus 兼容）"""
        logger.info(f"Replaying {len(events)} events...")
        
        for event in events:
            # 同步分发（模拟实时处理）
            asyncio.create_task(self._dispatch_event(event))
    
    def get_event_bus_stats(self) -> Dict:
        """获取事件总线统计（EventBus 兼容）"""
        return {
            "total_events": self._event_bus_stats["total_events"],
            "published_events": self._event_bus_stats["published_events"],
            "consumed_events": self._event_bus_stats["consumed_events"],
            "subscriptions": len(self._event_subscriptions.get("all", [])),
            "by_type": dict(self._event_bus_stats["by_type"]),
            "by_source": dict(self._event_bus_stats["by_source"])
        }
    
    def clear_event_history(self):
        """清空事件历史（EventBus 兼容）"""
        self._event_history.clear()
        logger.info("Event history cleared")


def get_runtime_bus() -> RuntimeBus:
    return RuntimeBus()


async def publish(topic: str, payload: Any, **kwargs) -> str:
    bus = get_runtime_bus()
    return await bus.publish(topic, payload, **kwargs)


async def publish_event(event_type: str, data: Dict[str, Any], **kwargs) -> str:
    bus = get_runtime_bus()
    return await bus.publish_event(event_type, data, **kwargs)


# ========================================================================
# EventBus 兼容工厂函数（用于平滑迁移）
# ========================================================================
def get_event_bus() -> RuntimeBus:
    """获取事件总线（兼容 EventBus 接口，返回 RuntimeBus 实例）"""
    logger.warning(
        "get_event_bus() is deprecated, use get_runtime_bus() instead. "
        "RuntimeBus now includes all EventBus functionality."
    )
    return get_runtime_bus()


async def publish_event_to_bus(event: Any):  # StandardEvent
    """快捷发布事件到总线（兼容 EventBus）"""
    bus = get_event_bus()
    await bus.publish_event(event)
