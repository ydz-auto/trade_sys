"""
Event Bus - 事件总线

核心功能：
- 统一事件分发
- 订阅/发布模式
- 事件过滤
- 异步处理
- 支持回测和 replay

事件流向：
StandardEvent ──→ EventBus ──┬──→ Strategy Engine
                            ├──→ Risk Engine
                            ├──→ Notification
                            └──→ Storage (回测)
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable, Type
import asyncio
from collections import defaultdict
import json
from pathlib import Path

from shared.contracts import StandardEvent, EventFilter, EventType, Source
from infrastructure.logging import get_logger

logger = get_logger("event_bus")


@dataclass
class Subscription:
    """订阅配置"""
    id: str
    name: str
    callback: Callable
    filter: Optional[EventFilter] = None
    priority: int = 0


class EventBus:
    """事件总线
    
    负责事件的路由、分发和处理。
    支持：
    - 订阅/发布模式
    - 事件过滤
    - 异步处理
    - 历史记录
    """
    
    def __init__(self, storage_path: str = None):
        self._subscriptions: Dict[str, List[Subscription]] = defaultdict(list)
        self._event_history: List[StandardEvent] = []
        self._max_history = 10000
        
        # 存储路径（用于回测 replay）
        self.storage_path = storage_path
        if storage_path:
            Path(storage_path).mkdir(parents=True, exist_ok=True)
        
        # 统计
        self._stats = {
            "total_events": 0,
            "published_events": 0,
            "consumed_events": 0,
            "by_type": defaultdict(int),
            "by_source": defaultdict(int)
        }
        
        logger.info("EventBus initialized")
    
    def subscribe(
        self,
        name: str,
        callback: Callable,
        filter: EventFilter = None,
        priority: int = 0
    ) -> str:
        """订阅事件
        
        Args:
            name: 订阅者名称
            callback: 回调函数
            filter: 事件过滤器（可选）
            priority: 优先级（高的先处理）
        
        Returns:
            订阅 ID
        """
        import uuid
        sub_id = str(uuid.uuid4())
        
        subscription = Subscription(
            id=sub_id,
            name=name,
            callback=callback,
            filter=filter,
            priority=priority
        )
        
        self._subscriptions["all"].append(subscription)
        
        # 按优先级排序
        self._subscriptions["all"].sort(key=lambda s: s.priority, reverse=True)
        
        logger.info(f"Subscribed: {name} (id={sub_id})")
        return sub_id
    
    def subscribe_by_type(
        self,
        event_type: EventType,
        name: str,
        callback: Callable,
        filter: EventFilter = None,
        priority: int = 0
    ) -> str:
        """订阅特定类型的事件"""
        sub_id = self.subscribe(name, callback, filter, priority)
        self._subscriptions["all"][-1].filter = EventFilter(event_types=[event_type])
        return sub_id
    
    def subscribe_by_source(
        self,
        source: Source,
        name: str,
        callback: Callable,
        filter: EventFilter = None,
        priority: int = 0
    ) -> str:
        """订阅特定来源的事件"""
        sub_id = self.subscribe(name, callback, filter, priority)
        self._subscriptions["all"][-1].filter = EventFilter(sources=[source])
        return sub_id
    
    def unsubscribe(self, sub_id: str):
        """取消订阅"""
        for subs in self._subscriptions.values():
            subs[:] = [s for s in subs if s.id != sub_id]
        logger.info(f"Unsubscribed: {sub_id}")
    
    async def publish(self, event: StandardEvent):
        """发布事件
        
        Args:
            event: 标准事件
        """
        self._stats["total_events"] += 1
        self._stats["by_type"][event.event_type] += 1
        self._stats["by_source"][event.source] += 1
        
        # 记录历史
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history.pop(0)
        
        # 保存到磁盘（用于回测）
        if self.storage_path:
            await self._save_event(event)
        
        # 分发给订阅者
        await self._dispatch(event)
        
        self._stats["published_events"] += 1
    
    async def publish_batch(self, events: List[StandardEvent]):
        """批量发布事件"""
        for event in events:
            await self.publish(event)
    
    async def _dispatch(self, event: StandardEvent):
        """分发事件给订阅者"""
        tasks = []
        
        for subscription in self._subscriptions["all"]:
            try:
                # 检查过滤器
                if subscription.filter and not subscription.filter.matches(event):
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
        
        self._stats["consumed_events"] += len(tasks)
    
    async def _save_event(self, event: StandardEvent):
        """保存事件到磁盘"""
        try:
            filename = f"{event.event_type}_{event.id}.json"
            filepath = Path(self.storage_path) / filename
            
            with open(filepath, "w") as f:
                json.dump(event.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save event: {e}")
    
    def get_history(
        self,
        event_type: str = None,
        source: str = None,
        limit: int = 100
    ) -> List[StandardEvent]:
        """获取历史事件"""
        events = self._event_history
        
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        if source:
            events = [e for e in events if e.source == source]
        
        return events[-limit:]
    
    def replay(self, events: List[StandardEvent]):
        """重放事件（用于回测）
        
        Args:
            events: 要重放的事件列表
        """
        logger.info(f"Replaying {len(events)} events...")
        
        for event in events:
            # 同步分发（模拟实时处理）
            asyncio.create_task(self._dispatch(event))
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "total_events": self._stats["total_events"],
            "published_events": self._stats["published_events"],
            "consumed_events": self._stats["consumed_events"],
            "subscriptions": len(self._subscriptions["all"]),
            "by_type": dict(self._stats["by_type"]),
            "by_source": dict(self._stats["by_source"])
        }
    
    def clear_history(self):
        """清空历史"""
        self._event_history.clear()
        logger.info("Event history cleared")


class StrategyEventHandler:
    """策略事件处理器"""
    
    def __init__(self, event_bus: EventBus, strategy_name: str):
        self.event_bus = event_bus
        self.strategy_name = strategy_name
        self._sub_id: Optional[str] = None
        self._events: List[StandardEvent] = []
    
    async def on_event(self, event: StandardEvent):
        """处理事件"""
        self._events.append(event)
        logger.info(f"[{self.strategy_name}] Received: {event.title[:50]}...")
    
    def subscribe(self, filter: EventFilter = None):
        """订阅事件"""
        self._sub_id = self.event_bus.subscribe(
            name=self.strategy_name,
            callback=self.on_event,
            filter=filter
        )
    
    def unsubscribe(self):
        """取消订阅"""
        if self._sub_id:
            self.event_bus.unsubscribe(self._sub_id)
    
    def get_recent_events(self, limit: int = 50) -> List[StandardEvent]:
        """获取最近事件"""
        return self._events[-limit:]


# 全局实例
_event_bus: Optional[EventBus] = None

def get_event_bus() -> EventBus:
    """获取事件总线"""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


async def publish_event(event: StandardEvent):
    """快捷发布事件"""
    bus = get_event_bus()
    await bus.publish(event)


async def publish_news(
    title: str,
    content: str,
    source: str,
    sentiment: str = "neutral",
    importance: float = 0.5,
    symbols: List[str] = None,
    tags: List[str] = None
):
    """快捷发布新闻事件"""
    from standard_event import create_news_event
    
    event = create_news_event(
        source=source,
        title=title,
        content=content,
        sentiment=sentiment,
        importance=importance,
        symbols=symbols,
        tags=tags
    )
    
    await publish_event(event)
