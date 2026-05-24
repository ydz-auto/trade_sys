"""
Subscription Manager - 订阅管理器

防止重复订阅，统一管理所有 WebSocket 订阅:

特性:
- 共享订阅（多个客户端订阅同一 topic 只推送一次）
- 订阅去重
- 客户端断开自动清理
- 订阅优先级
"""

import asyncio
from dataclasses import dataclass, field
from typing import Dict, Set, Optional, Any, List
from datetime import datetime
from collections import defaultdict
import time

from infrastructure.logging import get_logger
from infrastructure.utilities.priority_queue import EventPriority

logger = get_logger("infrastructure.runtime.subscription_manager")


@dataclass
class Subscription:
    topic: str
    subscriber_id: str
    filters: Dict[str, Any] = field(default_factory=dict)
    priority: EventPriority = EventPriority.P2_NORMAL
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)

    def touch(self) -> None:
        self.last_active = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "subscriber_id": self.subscriber_id,
            "filters": self.filters,
            "priority": self.priority.name,
            "created_at": self.created_at,
            "last_active": self.last_active,
        }


@dataclass
class TopicStats:
    total_subscriptions: int = 0
    active_subscribers: int = 0
    messages_sent: int = 0
    last_message_time: Optional[float] = None


class SubscriptionManager:
    def __init__(
        self,
        max_subscriptions_per_client: int = 50,
        max_total_subscriptions: int = 10000,
        inactive_timeout_seconds: float = 300.0,
    ):
        self._max_per_client = max_subscriptions_per_client
        self._max_total = max_total_subscriptions
        self._inactive_timeout = inactive_timeout_seconds
        
        self._topic_subscribers: Dict[str, Dict[str, Subscription]] = defaultdict(dict)
        self._subscriber_topics: Dict[str, Set[str]] = defaultdict(set)
        self._topic_stats: Dict[str, TopicStats] = defaultdict(TopicStats)
        
        self._total_subscriptions = 0
        self._total_messages = 0
        self._lock = asyncio.Lock()

    async def subscribe(self, subscription: Subscription) -> bool:
        async with self._lock:
            return self._do_subscribe(subscription)

    def subscribe_sync(self, subscription: Subscription) -> bool:
        return self._do_subscribe(subscription)

    def _do_subscribe(self, subscription: Subscription) -> bool:
        topic = subscription.topic
        sid = subscription.subscriber_id
        
        if len(self._subscriber_topics[sid]) >= self._max_per_client:
            logger.warning(
                f"Subscriber {sid} reached max subscriptions "
                f"({self._max_per_client})"
            )
            return False
        
        if self._total_subscriptions >= self._max_total:
            logger.warning("Total subscriptions limit reached")
            return False
        
        if sid in self._topic_subscribers[topic]:
            existing = self._topic_subscribers[topic][sid]
            existing.touch()
            return True
        
        self._topic_subscribers[topic][sid] = subscription
        self._subscriber_topics[sid].add(topic)
        self._total_subscriptions += 1
        
        self._topic_stats[topic].total_subscriptions += 1
        self._topic_stats[topic].active_subscribers = len(
            self._topic_subscribers[topic]
        )
        
        logger.debug(f"Subscribed: {sid} -> {topic}")
        return True

    async def unsubscribe(
        self,
        subscriber_id: str,
        topic: Optional[str] = None,
    ) -> int:
        async with self._lock:
            return self._do_unsubscribe(subscriber_id, topic)

    def unsubscribe_sync(
        self,
        subscriber_id: str,
        topic: Optional[str] = None,
    ) -> int:
        return self._do_unsubscribe(subscriber_id, topic)

    def _do_unsubscribe(
        self,
        subscriber_id: str,
        topic: Optional[str] = None,
    ) -> int:
        if topic:
            topics_to_remove = {topic}
        else:
            topics_to_remove = self._subscriber_topics.get(subscriber_id, set()).copy()
        
        removed_count = 0
        for t in topics_to_remove:
            if subscriber_id in self._topic_subscribers[t]:
                del self._topic_subscribers[t][subscriber_id]
                self._total_subscriptions -= 1
                removed_count += 1
                
                self._topic_stats[t].active_subscribers = len(
                    self._topic_subscribers[t]
                )
        
        if topic is None:
            self._subscriber_topics.pop(subscriber_id, None)
        else:
            self._subscriber_topics[subscriber_id].discard(topic)
        
        if removed_count > 0:
            logger.debug(f"Unsubscribed: {subscriber_id} from {removed_count} topics")
        
        return removed_count

    async def disconnect_client(self, subscriber_id: str) -> int:
        return await self.unsubscribe(subscriber_id)

    def get_subscribers(self, topic: str) -> List[str]:
        return list(self._topic_subscribers.get(topic, {}).keys())

    def get_subscriptions(self, subscriber_id: str) -> List[str]:
        return list(self._subscriber_topics.get(subscriber_id, set()))

    def get_subscription_details(
        self,
        topic: str,
        subscriber_id: str,
    ) -> Optional[Subscription]:
        return self._topic_subscribers.get(topic, {}).get(subscriber_id)

    def is_subscribed(self, topic: str, subscriber_id: str) -> bool:
        return subscriber_id in self._topic_subscribers.get(topic, {})

    def has_subscribers(self, topic: str) -> bool:
        return bool(self._topic_subscribers.get(topic))

    def get_active_topics(self) -> Set[str]:
        return {
            topic
            for topic, subs in self._topic_subscribers.items()
            if subs
        }

    def should_push(self, topic: str) -> bool:
        return self.has_subscribers(topic)

    def record_message_sent(self, topic: str, count: int = 1) -> None:
        self._total_messages += count
        stats = self._topic_stats[topic]
        stats.messages_sent += count
        stats.last_message_time = time.time()

    def get_topic_stats(self, topic: str) -> Dict[str, Any]:
        stats = self._topic_stats[topic]
        return {
            "topic": topic,
            "total_subscriptions": stats.total_subscriptions,
            "active_subscribers": stats.active_subscribers,
            "messages_sent": stats.messages_sent,
            "last_message_time": stats.last_message_time,
        }

    async def cleanup_inactive(self) -> int:
        async with self._lock:
            now = time.time()
            inactive_threshold = now - self._inactive_timeout
            
            inactive_subscribers = []
            for sid, topics in self._subscriber_topics.items():
                for topic in topics:
                    sub = self._topic_subscribers.get(topic, {}).get(sid)
                    if sub and sub.last_active < inactive_threshold:
                        inactive_subscribers.append(sid)
                        break
            
            removed = 0
            for sid in inactive_subscribers:
                removed += self._do_unsubscribe(sid)
            
            if removed > 0:
                logger.info(f"Cleaned up {removed} inactive subscriptions")
            
            return removed

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_subscriptions": self._total_subscriptions,
            "total_messages": self._total_messages,
            "active_topics": len(self.get_active_topics()),
            "total_subscribers": len(self._subscriber_topics),
            "topic_stats": {
                topic: self.get_topic_stats(topic)
                for topic in self.get_active_topics()
            },
            "config": {
                "max_per_client": self._max_per_client,
                "max_total": self._max_total,
                "inactive_timeout": self._inactive_timeout,
            },
        }

    def clear(self) -> None:
        self._topic_subscribers.clear()
        self._subscriber_topics.clear()
        self._topic_stats.clear()
        self._total_subscriptions = 0
        self._total_messages = 0


class TopicRegistry:
    DASHBOARD = "channel:dashboard"
    DECISION = "channel:decision"
    RISK = "channel:risk"
    POSITION = "channel:position"
    TIMELINE = "channel:timeline"
    SIGNAL = "channel:signal"
    ORDER = "channel:order"
    PRICE = "channel:price"
    FACTOR = "channel:factor"
    NEWS = "channel:news"
    AI = "channel:ai"
    REPLAY = "channel:replay"
    
    CRITICAL_TOPICS = {ORDER, RISK, POSITION}
    HIGH_PRIORITY_TOPICS = {PRICE, SIGNAL, DECISION}
    NORMAL_PRIORITY_TOPICS = {DASHBOARD, FACTOR, TIMELINE}
    LOW_PRIORITY_TOPICS = {NEWS, AI, REPLAY}
    
    @classmethod
    def all(cls) -> List[str]:
        return [
            cls.DASHBOARD,
            cls.DECISION,
            cls.RISK,
            cls.POSITION,
            cls.TIMELINE,
            cls.SIGNAL,
            cls.ORDER,
            cls.PRICE,
            cls.FACTOR,
            cls.NEWS,
            cls.AI,
            cls.REPLAY,
        ]
    
    @classmethod
    def get_priority(cls, topic: str) -> EventPriority:
        if topic in cls.CRITICAL_TOPICS:
            return EventPriority.P0_CRITICAL
        if topic in cls.HIGH_PRIORITY_TOPICS:
            return EventPriority.P1_HIGH
        if topic in cls.NORMAL_PRIORITY_TOPICS:
            return EventPriority.P2_NORMAL
        if topic in cls.LOW_PRIORITY_TOPICS:
            return EventPriority.P3_LOW
        return EventPriority.P2_NORMAL
