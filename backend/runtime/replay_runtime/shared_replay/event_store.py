"""
Event Store - 事件存储（Facade）

提供事件溯源能力，支持回放和重建。
底层委托给 infrastructure.persistence.repository.replay.event_store_repository。
"""

from typing import Dict, List, Optional, Any, AsyncIterator
from datetime import datetime
import asyncio
import uuid

from infrastructure.logging import get_logger
from infrastructure.persistence.repository.replay.event_store_repository import (
    EventStoreRepository,
    get_event_store_repository,
)

from runtime.replay_runtime.models.models import EventRecord, EventType, ReplayCheckpoint

logger = get_logger("shared.replay.event_store")


class EventStore:

    def __init__(self):
        self._repo: Optional[EventStoreRepository] = None
        self._initialized = False

    async def initialize(self):
        if self._initialized:
            return

        self._repo = await get_event_store_repository()
        self._initialized = True
        logger.info("EventStore initialized (delegating to EventStoreRepository)")

    async def append(
        self,
        event_type: EventType,
        exchange: str,
        symbol: str,
        timestamp: int,
        data: Dict[str, Any],
        sequence: int = 0,
        partition: int = 0,
    ) -> str:
        return await self._repo.append(
            event_type=event_type.value,
            exchange=exchange,
            symbol=symbol,
            timestamp=timestamp,
            data=data,
            sequence=sequence,
            partition=partition,
        )

    async def append_batch(self, events: List[EventRecord]) -> int:
        if not events:
            return 0

        import json
        rows = []
        for event in events:
            rows.append({
                "event_id": event.event_id,
                "event_type": event.event_type.value,
                "exchange": event.exchange,
                "symbol": event.symbol,
                "timestamp": event.timestamp,
                "sequence": event.sequence,
                "partition": event.partition,
                "data": json.dumps(event.data),
                "created_at": event.created_at,
            })

        return await self._repo.append_batch(rows)

    async def read_events(
        self,
        exchange: str,
        symbol: str,
        event_type: EventType,
        start_time: int,
        end_time: int,
        limit: int = 10000,
    ) -> List[EventRecord]:
        raw_events = await self._repo.read_events(
            exchange=exchange,
            symbol=symbol,
            event_type=event_type.value,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )

        events = []
        for raw in raw_events:
            events.append(EventRecord(
                event_id=raw["event_id"],
                event_type=EventType(raw["event_type"]),
                exchange=raw["exchange"],
                symbol=raw["symbol"],
                timestamp=raw["timestamp"],
                sequence=raw["sequence"],
                partition=raw["partition"],
                data=raw["data"],
                created_at=raw["created_at"],
            ))
        return events

    async def stream_events(
        self,
        exchange: str,
        symbol: str,
        event_type: EventType,
        start_time: int,
        end_time: int,
        batch_size: int = 1000,
    ) -> AsyncIterator[List[EventRecord]]:
        current_time = start_time

        while current_time < end_time:
            events = await self.read_events(
                exchange, symbol, event_type,
                current_time, end_time,
                limit=batch_size
            )

            if not events:
                break

            yield events

            current_time = events[-1].timestamp + 1

    async def get_latest_timestamp(
        self,
        exchange: str,
        symbol: str,
        event_type: EventType,
    ) -> Optional[int]:
        return await self._repo.get_latest_timestamp(
            exchange=exchange,
            symbol=symbol,
            event_type=event_type.value,
        )

    async def get_event_count(
        self,
        exchange: str,
        symbol: str,
        event_type: EventType,
        start_time: int,
        end_time: int,
    ) -> int:
        return await self._repo.get_event_count(
            exchange=exchange,
            symbol=symbol,
            event_type=event_type.value,
            start_time=start_time,
            end_time=end_time,
        )

    async def save_checkpoint(self, checkpoint: ReplayCheckpoint):
        await self._repo.save_checkpoint(checkpoint.to_dict())

    async def load_checkpoint(
        self,
        replay_id: str,
        exchange: str,
        symbol: str,
        timeframe: str,
    ) -> Optional[ReplayCheckpoint]:
        raw = await self._repo.load_checkpoint(
            replay_id=replay_id,
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
        )

        if raw:
            return ReplayCheckpoint(
                checkpoint_id=raw["checkpoint_id"],
                replay_id=raw["replay_id"],
                exchange=raw["exchange"],
                symbol=raw["symbol"],
                timeframe=raw["timeframe"],
                last_timestamp=raw["last_timestamp"],
                last_sequence=raw["last_sequence"],
                processed_count=raw["processed_count"],
                created_at=raw["created_at"],
                metadata=raw.get("metadata", {}),
            )
        return None

    async def delete_events(
        self,
        exchange: str,
        symbol: str,
        event_type: EventType,
        before_time: int,
    ) -> int:
        return await self._repo.delete_events(
            exchange=exchange,
            symbol=symbol,
            event_type=event_type.value,
            before_time=before_time,
        )


_event_store: Optional[EventStore] = None


async def get_event_store() -> EventStore:
    global _event_store
    if _event_store is None:
        _event_store = EventStore()
        await _event_store.initialize()
    return _event_store
