"""
Real-time Push - WebSocket 实时推送模块
支持热词推送和订阅
"""
import asyncio
import json
from typing import Dict, List, Set, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from collections import defaultdict

from infrastructure.logging import get_logger

logger = get_logger("pipeline.realtime")


class MessageType(Enum):
    """消息类型"""
    NEWS = "news"
    PRICE = "price"
    ALERT = "alert"
    SYSTEM = "system"


@dataclass
class PushMessage:
    """推送消息"""
    type: MessageType
    data: Any
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    priority: int = 1
    metadata: Dict = field(default_factory=dict)


@dataclass
class Subscription:
    """订阅"""
    subscriber_id: str
    channels: Set[str]
    filters: Dict = field(default_factory=dict)
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    last_active: float = field(default_factory=lambda: datetime.now().timestamp())


@dataclass
class PushResult:
    """推送结果"""
    success: bool
    delivered: int
    failed: int
    subscribers_count: int


class RealtimePusher:
    """实时推送器
    
    支持：
    - 多频道推送
    - 关键词/热词订阅
    - 优先级队列
    - 离线消息缓存
    - 连接管理
    """
    
    def __init__(
        self,
        max_queue_size: int = 1000,
        message_ttl: int = 3600,
        heartbeat_interval: int = 30
    ):
        self.max_queue_size = max_queue_size
        self.message_ttl = message_ttl
        self.heartbeat_interval = heartbeat_interval
        
        self._subscriptions: Dict[str, Subscription] = {}
        self._channels: Dict[str, Set[str]] = defaultdict(set)
        self._keyword_subscriptions: Dict[str, Set[str]] = defaultdict(set)
        self._message_queues: Dict[str, asyncio.Queue] = {}
        self._broadcast_queues: List[asyncio.Queue] = []
        self._callbacks: Dict[str, List[Callable]] = defaultdict(list)
        
        self._running = False
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._stats = {
            "total_messages": 0,
            "total_pushes": 0,
            "total_subscribers": 0
        }
    
    def subscribe(
        self,
        subscriber_id: str,
        channels: List[str] = None,
        keywords: List[str] = None,
        filters: Dict = None
    ) -> Subscription:
        """订阅频道或关键词"""
        if channels is None:
            channels = []
        if keywords is None:
            keywords = []
        
        for channel in channels:
            self._channels[channel].add(subscriber_id)
        
        for keyword in keywords:
            self._keyword_subscriptions[keyword.lower()].add(subscriber_id)
        
        subscription = Subscription(
            subscriber_id=subscriber_id,
            channels=set(channels),
            filters=filters or {},
            created_at=datetime.now().timestamp()
        )
        
        self._subscriptions[subscriber_id] = subscription
        
        if subscriber_id not in self._message_queues:
            self._message_queues[subscriber_id] = asyncio.Queue(maxsize=self.max_queue_size)
        
        self._stats["total_subscribers"] = len(self._subscriptions)
        
        logger.info(f"Subscriber {subscriber_id} subscribed to {len(channels)} channels and {len(keywords)} keywords")
        
        return subscription
    
    def unsubscribe(self, subscriber_id: str, channels: List[str] = None):
        """取消订阅"""
        if subscriber_id not in self._subscriptions:
            return
        
        subscription = self._subscriptions[subscriber_id]
        
        if channels:
            for channel in channels:
                if channel in self._channels:
                    self._channels[channel].discard(subscriber_id)
                subscription.channels.discard(channel)
        else:
            for channel in list(subscription.channels):
                if channel in self._channels:
                    self._channels[channel].discard(subscriber_id)
            subscription.channels.clear()
            
            for keyword, subs in self._keyword_subscriptions.items():
                subs.discard(subscriber_id)
            
            del self._subscriptions[subscriber_id]
            if subscriber_id in self._message_queues:
                del self._message_queues[subscriber_id]
        
        self._stats["total_subscribers"] = len(self._subscriptions)
        
        logger.info(f"Subscriber {subscriber_id} unsubscribed")
    
    def push(
        self,
        message: PushMessage
    ) -> PushResult:
        """推送消息"""
        self._stats["total_messages"] += 1
        
        target_subscribers = set()
        
        if message.type.value in self._channels:
            target_subscribers.update(self._channels[message.type.value])
        
        if message.type == MessageType.NEWS and isinstance(message.data, dict):
            content = f"{message.data.get('title', '')} {message.data.get('content', '')}".lower()
            
            for keyword, subscribers in self._keyword_subscriptions.items():
                if keyword in content:
                    target_subscribers.update(subscribers)
        
        delivered = 0
        failed = 0
        
        for subscriber_id in target_subscribers:
            if subscriber_id in self._message_queues:
                try:
                    self._message_queues[subscriber_id].put_nowait(message)
                    delivered += 1
                except asyncio.QueueFull:
                    failed += 1
            elif subscriber_id in self._broadcast_queues:
                try:
                    self._broadcast_queues[self._broadcast_queues.index(subscriber_id)].put_nowait(message)
                    delivered += 1
                except asyncio.QueueFull:
                    failed += 1
        
        for callback in self._callbacks.get(message.type.value, []):
            try:
                callback(message)
            except Exception as e:
                logger.error(f"Callback error: {e}")
        
        self._stats["total_pushes"] += delivered
        
        return PushResult(
            success=failed == 0,
            delivered=delivered,
            failed=failed,
            subscribers_count=len(target_subscribers)
        )
    
    def push_news(
        self,
        news_data: Dict,
        priority: int = 1,
        metadata: Dict = None
    ) -> PushResult:
        """推送新闻"""
        message = PushMessage(
            type=MessageType.NEWS,
            data=news_data,
            priority=priority,
            metadata=metadata or {}
        )
        return self.push(message)
    
    def push_price(
        self,
        price_data: Dict,
        priority: int = 1
    ) -> PushResult:
        """推送价格"""
        message = PushMessage(
            type=MessageType.PRICE,
            data=price_data,
            priority=priority
        )
        return self.push(message)
    
    def push_alert(
        self,
        alert_data: Dict,
        priority: int = 1
    ) -> PushResult:
        """推送告警"""
        message = PushMessage(
            type=MessageType.ALERT,
            data=alert_data,
            priority=priority
        )
        return self.push(message)
    
    def register_callback(
        self,
        message_type: str,
        callback: Callable
    ):
        """注册回调"""
        self._callbacks[message_type].append(callback)
    
    async def get_message(
        self,
        subscriber_id: str,
        timeout: float = None
    ) -> Optional[PushMessage]:
        """获取消息（阻塞）"""
        if subscriber_id not in self._message_queues:
            return None
        
        try:
            if timeout:
                message = await asyncio.wait_for(
                    self._message_queues[subscriber_id].get(),
                    timeout=timeout
                )
            else:
                message = await self._message_queues[subscriber_id].get()
            
            if subscriber_id in self._subscriptions:
                self._subscriptions[subscriber_id].last_active = datetime.now().timestamp()
            
            return message
        except asyncio.TimeoutError:
            return None
    
    async def get_messages_batch(
        self,
        subscriber_id: str,
        max_count: int = 10,
        timeout: float = 1.0
    ) -> List[PushMessage]:
        """批量获取消息"""
        messages = []
        
        if subscriber_id not in self._message_queues:
            return messages
        
        end_time = asyncio.get_event_loop().time() + timeout
        
        for _ in range(max_count):
            remaining = end_time - asyncio.get_event_loop().time()
            if remaining <= 0:
                break
            
            try:
                message = await asyncio.wait_for(
                    self._message_queues[subscriber_id].get(),
                    timeout=remaining
                )
                messages.append(message)
            except asyncio.TimeoutError:
                break
        
        if messages and subscriber_id in self._subscriptions:
            self._subscriptions[subscriber_id].last_active = datetime.now().timestamp()
        
        return messages
    
    async def start_heartbeat(self):
        """启动心跳"""
        self._running = True
        
        async def heartbeat():
            while self._running:
                try:
                    await asyncio.sleep(self.heartbeat_interval)
                    
                    inactive_cutoff = datetime.now().timestamp() - 300
                    
                    inactive = [
                        sid for sid, sub in self._subscriptions.items()
                        if sub.last_active < inactive_cutoff
                    ]
                    
                    for sid in inactive:
                        logger.info(f"Removing inactive subscriber: {sid}")
                        self.unsubscribe(sid)
                    
                    if inactive:
                        logger.info(f"Removed {len(inactive)} inactive subscribers")
                        
                except Exception as e:
                    logger.error(f"Heartbeat error: {e}")
        
        self._heartbeat_task = asyncio.create_task(heartbeat())
    
    async def stop_heartbeat(self):
        """停止心跳"""
        self._running = False
        
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
    
    def get_stats(self) -> Dict:
        """获取统计"""
        queue_sizes = {
            sid: q.qsize()
            for sid, q in self._message_queues.items()
        }
        
        return {
            "total_messages": self._stats["total_messages"],
            "total_pushes": self._stats["total_pushes"],
            "total_subscribers": self._stats["total_subscribers"],
            "channels_count": len(self._channels),
            "keyword_subscriptions_count": len(self._keyword_subscriptions),
            "queues_with_pending": sum(1 for size in queue_sizes.values() if size > 0),
            "total_pending_messages": sum(queue_sizes.values())
        }
    
    def get_subscribers(self) -> Dict:
        """获取订阅者列表"""
        return {
            sid: {
                "channels": list(sub.channels),
                "keywords": [
                    kw for kw, subs in self._keyword_subscriptions.items()
                    if sid in subs
                ],
                "last_active": sub.last_active,
                "queue_size": self._message_queues.get(sid, asyncio.Queue()).qsize()
            }
            for sid, sub in self._subscriptions.items()
        }


_pusher: Optional[RealtimePusher] = None

def get_pusher() -> RealtimePusher:
    """获取推送器单例"""
    global _pusher
    if _pusher is None:
        _pusher = RealtimePusher()
    return _pusher
