"""
Priority Event Queue - 优先级事件队列

事件优先级:
- P0_CRITICAL: liquidation warning, order filled, execution error
- P1_HIGH: price tick, risk update, position change
- P2_NORMAL: factor update, signal update
- P3_LOW: AI summary, sentiment
- P4_BACKGROUND: replay visualization, analytics

特性:
- 优先级队列，高优先级事件优先处理
- 队列满时自动丢弃低优先级事件
- 统计丢弃事件数量
"""

import asyncio
import os
from enum import IntEnum
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Callable, Awaitable
from collections import defaultdict
from datetime import datetime
import time

from infrastructure.logging import get_logger

logger = get_logger("infrastructure.priority_queue")


class EventPriority(IntEnum):
    P0_CRITICAL = 0
    P1_HIGH = 1
    P2_NORMAL = 2
    P3_LOW = 3
    P4_BACKGROUND = 4

    @classmethod
    def from_name(cls, name: str) -> "EventPriority":
        name_map = {
            "critical": cls.P0_CRITICAL,
            "high": cls.P1_HIGH,
            "normal": cls.P2_NORMAL,
            "low": cls.P3_LOW,
            "background": cls.P4_BACKGROUND,
        }
        return name_map.get(name.lower(), cls.P2_NORMAL)


@dataclass
class PrioritizedEvent:
    priority: EventPriority
    event_type: str
    payload: Any
    timestamp: float = field(default_factory=time.time)
    source: str = "unknown"
    drop_on_overload: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "priority": self.priority.value,
            "priority_name": self.priority.name,
            "event_type": self.event_type,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "source": self.source,
            "metadata": self.metadata,
        }


class PriorityEventQueue:
    def __init__(
        self,
        max_size_per_priority: int = int(os.environ.get("PQ_MAX_SIZE_PER_PRIORITY", "1000")),
        total_max_size: int = int(os.environ.get("PQ_TOTAL_MAX_SIZE", "10000")),
    ):
        self._queues: Dict[EventPriority, asyncio.Queue] = {
            priority: asyncio.Queue(maxsize=max_size_per_priority)
            for priority in EventPriority
        }
        self._total_max_size = total_max_size
        self._drop_stats: Dict[EventPriority, int] = defaultdict(int)
        self._processed_stats: Dict[EventPriority, int] = defaultdict(int)
        self._total_enqueued = 0
        self._total_dropped = 0
        self._lock = asyncio.Lock()

    async def push(self, event: PrioritizedEvent) -> bool:
        queue = self._queues[event.priority]
        
        async with self._lock:
            if self._total_enqueued >= self._total_max_size:
                if event.drop_on_overload and event.priority > EventPriority.P0_CRITICAL:
                    self._drop_stats[event.priority] += 1
                    self._total_dropped += 1
                    logger.warning(
                        f"Queue full, dropped event: {event.event_type} "
                        f"(priority={event.priority.name})"
                    )
                    return False
            
            try:
                queue.put_nowait(event)
                self._total_enqueued += 1
                return True
            except asyncio.QueueFull:
                if event.drop_on_overload and event.priority > EventPriority.P0_CRITICAL:
                    self._drop_stats[event.priority] += 1
                    self._total_dropped += 1
                    logger.warning(
                        f"Priority queue full, dropped event: {event.event_type} "
                        f"(priority={event.priority.name})"
                    )
                    return False
                raise

    def push_nowait(self, event: PrioritizedEvent) -> bool:
        queue = self._queues[event.priority]
        
        if self._total_enqueued >= self._total_max_size:
            if event.drop_on_overload and event.priority > EventPriority.P0_CRITICAL:
                self._drop_stats[event.priority] += 1
                self._total_dropped += 1
                return False
        
        try:
            queue.put_nowait(event)
            self._total_enqueued += 1
            return True
        except asyncio.QueueFull:
            if event.drop_on_overload and event.priority > EventPriority.P0_CRITICAL:
                self._drop_stats[event.priority] += 1
                self._total_dropped += 1
                return False
            raise

    async def pop(self, timeout: float = 0.001) -> Optional[PrioritizedEvent]:
        for priority in EventPriority:
            queue = self._queues[priority]
            if not queue.empty():
                try:
                    event = queue.get_nowait()
                    self._processed_stats[priority] += 1
                    self._total_enqueued -= 1
                    return event
                except asyncio.QueueEmpty:
                    continue
        
        await asyncio.sleep(timeout)
        return None

    def pop_nowait(self) -> Optional[PrioritizedEvent]:
        for priority in EventPriority:
            queue = self._queues[priority]
            if not queue.empty():
                try:
                    event = queue.get_nowait()
                    self._processed_stats[priority] += 1
                    self._total_enqueued -= 1
                    return event
                except asyncio.QueueEmpty:
                    continue
        return None

    async def pop_batch(self, batch_size: int = 100) -> list[PrioritizedEvent]:
        events = []
        for _ in range(batch_size):
            event = self.pop_nowait()
            if event:
                events.append(event)
            else:
                break
        return events

    def size(self, priority: Optional[EventPriority] = None) -> int:
        if priority:
            return self._queues[priority].qsize()
        return sum(q.qsize() for q in self._queues.values())

    def is_empty(self) -> bool:
        return all(q.empty() for q in self._queues.values())

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_enqueued": self._total_enqueued,
            "total_dropped": self._total_dropped,
            "current_size": self.size(),
            "drop_by_priority": {
                p.name: self._drop_stats[p] for p in EventPriority
            },
            "processed_by_priority": {
                p.name: self._processed_stats[p] for p in EventPriority
            },
            "queue_sizes": {
                p.name: self._queues[p].qsize() for p in EventPriority
            },
        }

    def clear(self):
        for priority in EventPriority:
            while not self._queues[priority].empty():
                try:
                    self._queues[priority].get_nowait()
                except asyncio.QueueEmpty:
                    break
        self._total_enqueued = 0

    async def process_with_handler(
        self,
        handler: Callable[[PrioritizedEvent], Awaitable[None]],
        batch_size: int = 10,
    ):
        events = await self.pop_batch(batch_size)
        for event in events:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Error processing event {event.event_type}: {e}")
