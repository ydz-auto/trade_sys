"""
Event Store - 事件存储
提供事件溯源能力，支持回放和重建
"""

from typing import Dict, List, Optional, Any, AsyncIterator
from datetime import datetime
import asyncio
import uuid

from infrastructure.logging import get_logger
from infrastructure.database import ClickHouseManager

from .models import EventRecord, EventType, ReplayCheckpoint

logger = get_logger("shared.replay.event_store")


class EventStore:
    """事件存储

    提供事件的持久化和检索能力
    """

    TABLE_NAME = "event_store"

    def __init__(self):
        self.clickhouse: Optional[ClickHouseManager] = None
        self._initialized = False

    async def initialize(self):
        """初始化"""
        if self._initialized:
            return

        self.clickhouse = ClickHouseManager()
        await self._ensure_table()
        self._initialized = True
        logger.info("EventStore initialized")

    async def _ensure_table(self):
        """确保表存在"""
        create_sql = f"""
        CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
            event_id String,
            event_type String,
            exchange String,
            symbol String,
            timestamp Int64,
            sequence Int64,
            partition Int32,
            data String,
            created_at Int64
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(fromUnixTimestamp64Milli(timestamp))
        ORDER BY (exchange, symbol, event_type, timestamp, sequence)
        """
        try:
            await self.clickhouse.execute(create_sql)
        except Exception as e:
            logger.warning(f"Table creation warning: {e}")

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
        """追加事件"""
        event_id = str(uuid.uuid4())

        import json
        data_json = json.dumps(data)

        try:
            await self.clickhouse.execute(
                f"""
                INSERT INTO {self.TABLE_NAME} (
                    event_id, event_type, exchange, symbol,
                    timestamp, sequence, partition, data, created_at
                ) VALUES
                """,
                [{
                    "event_id": event_id,
                    "event_type": event_type.value,
                    "exchange": exchange,
                    "symbol": symbol,
                    "timestamp": timestamp,
                    "sequence": sequence,
                    "partition": partition,
                    "data": data_json,
                    "created_at": int(datetime.now().timestamp() * 1000),
                }]
            )
            return event_id
        except Exception as e:
            logger.error(f"Failed to append event: {e}")
            raise

    async def append_batch(self, events: List[EventRecord]) -> int:
        """批量追加事件"""
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

        try:
            await self.clickhouse.execute(
                f"""
                INSERT INTO {self.TABLE_NAME} (
                    event_id, event_type, exchange, symbol,
                    timestamp, sequence, partition, data, created_at
                ) VALUES
                """,
                rows
            )
            return len(events)
        except Exception as e:
            logger.error(f"Failed to append batch: {e}")
            raise

    async def read_events(
        self,
        exchange: str,
        symbol: str,
        event_type: EventType,
        start_time: int,
        end_time: int,
        limit: int = 10000,
    ) -> List[EventRecord]:
        """读取事件"""
        try:
            rows = await self.clickhouse.execute(
                f"""
                SELECT event_id, event_type, exchange, symbol,
                       timestamp, sequence, partition, data, created_at
                FROM {self.TABLE_NAME}
                WHERE exchange = %(exchange)s
                AND symbol = %(symbol)s
                AND event_type = %(event_type)s
                AND timestamp >= %(start_time)s
                AND timestamp < %(end_time)s
                ORDER BY timestamp, sequence
                LIMIT %(limit)s
                """,
                {
                    "exchange": exchange,
                    "symbol": symbol,
                    "event_type": event_type.value,
                    "start_time": start_time,
                    "end_time": end_time,
                    "limit": limit,
                }
            )

            import json
            events = []
            for row in rows:
                events.append(EventRecord(
                    event_id=row[0],
                    event_type=EventType(row[1]),
                    exchange=row[2],
                    symbol=row[3],
                    timestamp=row[4],
                    sequence=row[5],
                    partition=row[6],
                    data=json.loads(row[7]) if row[7] else {},
                    created_at=row[8],
                ))
            return events
        except Exception as e:
            logger.error(f"Failed to read events: {e}")
            return []

    async def stream_events(
        self,
        exchange: str,
        symbol: str,
        event_type: EventType,
        start_time: int,
        end_time: int,
        batch_size: int = 1000,
    ) -> AsyncIterator[List[EventRecord]]:
        """流式读取事件"""
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
        """获取最新时间戳"""
        try:
            rows = await self.clickhouse.execute(
                f"""
                SELECT max(timestamp) FROM {self.TABLE_NAME}
                WHERE exchange = %(exchange)s
                AND symbol = %(symbol)s
                AND event_type = %(event_type)s
                """,
                {
                    "exchange": exchange,
                    "symbol": symbol,
                    "event_type": event_type.value,
                }
            )

            if rows and rows[0][0]:
                return rows[0][0]
            return None
        except Exception as e:
            logger.error(f"Failed to get latest timestamp: {e}")
            return None

    async def get_event_count(
        self,
        exchange: str,
        symbol: str,
        event_type: EventType,
        start_time: int,
        end_time: int,
    ) -> int:
        """获取事件数量"""
        try:
            rows = await self.clickhouse.execute(
                f"""
                SELECT count() FROM {self.TABLE_NAME}
                WHERE exchange = %(exchange)s
                AND symbol = %(symbol)s
                AND event_type = %(event_type)s
                AND timestamp >= %(start_time)s
                AND timestamp < %(end_time)s
                """,
                {
                    "exchange": exchange,
                    "symbol": symbol,
                    "event_type": event_type.value,
                    "start_time": start_time,
                    "end_time": end_time,
                }
            )

            if rows:
                return rows[0][0]
            return 0
        except Exception as e:
            logger.error(f"Failed to get event count: {e}")
            return 0

    async def save_checkpoint(self, checkpoint: ReplayCheckpoint):
        """保存检查点"""
        try:
            await self.clickhouse.execute(
                """
                INSERT INTO replay_checkpoints (
                    checkpoint_id, replay_id, exchange, symbol, timeframe,
                    last_timestamp, last_sequence, processed_count,
                    created_at, metadata
                ) VALUES
                """,
                [checkpoint.to_dict()]
            )
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")

    async def load_checkpoint(
        self,
        replay_id: str,
        exchange: str,
        symbol: str,
        timeframe: str,
    ) -> Optional[ReplayCheckpoint]:
        """加载检查点"""
        try:
            rows = await self.clickhouse.execute(
                """
                SELECT * FROM replay_checkpoints
                WHERE replay_id = %(replay_id)s
                AND exchange = %(exchange)s
                AND symbol = %(symbol)s
                AND timeframe = %(timeframe)s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                {
                    "replay_id": replay_id,
                    "exchange": exchange,
                    "symbol": symbol,
                    "timeframe": timeframe,
                }
            )

            if rows:
                return ReplayCheckpoint(
                    checkpoint_id=rows[0][0],
                    replay_id=rows[0][1],
                    exchange=rows[0][2],
                    symbol=rows[0][3],
                    timeframe=rows[0][4],
                    last_timestamp=rows[0][5],
                    last_sequence=rows[0][6],
                    processed_count=rows[0][7],
                    created_at=rows[0][8],
                    metadata=rows[0][9] if len(rows[0]) > 9 else {},
                )
            return None
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return None

    async def delete_events(
        self,
        exchange: str,
        symbol: str,
        event_type: EventType,
        before_time: int,
    ) -> int:
        """删除旧事件"""
        try:
            await self.clickhouse.execute(
                f"""
                ALTER TABLE {self.TABLE_NAME} DELETE
                WHERE exchange = %(exchange)s
                AND symbol = %(symbol)s
                AND event_type = %(event_type)s
                AND timestamp < %(before_time)s
                """,
                {
                    "exchange": exchange,
                    "symbol": symbol,
                    "event_type": event_type.value,
                    "before_time": before_time,
                }
            )
            return 0
        except Exception as e:
            logger.error(f"Failed to delete events: {e}")
            return 0


_event_store: Optional[EventStore] = None


async def get_event_store() -> EventStore:
    """获取事件存储实例"""
    global _event_store
    if _event_store is None:
        _event_store = EventStore()
        await _event_store.initialize()
    return _event_store
