"""
Event Store Repository - 事件溯源存储

提供事件的持久化和检索能力，支持回放和重建。
从 runtime/replay_runtime 迁入 infrastructure/persistence/repository/replay/。
"""

from typing import Dict, List, Optional, Any, AsyncIterator
from datetime import datetime
import asyncio
import uuid

from infrastructure.logging import get_logger
from infrastructure.persistence.database.clickhouse import ClickHouseManager

logger = get_logger("infrastructure.persistence.repository.replay.event_store")


class EventStoreRepository:

    TABLE_NAME = "event_store"

    def __init__(self):
        self.clickhouse: Optional[ClickHouseManager] = None
        self._initialized = False

    async def initialize(self):
        if self._initialized:
            return

        self.clickhouse = ClickHouseManager()
        await self._ensure_table()
        self._initialized = True
        logger.info("EventStoreRepository initialized")

    async def _ensure_table(self):
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
        event_type: str,
        exchange: str,
        symbol: str,
        timestamp: int,
        data: Dict[str, Any],
        sequence: int = 0,
        partition: int = 0,
    ) -> str:
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
                    "event_type": event_type,
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

    async def append_batch(self, rows: List[Dict[str, Any]]) -> int:
        if not rows:
            return 0

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
            return len(rows)
        except Exception as e:
            logger.error(f"Failed to append batch: {e}")
            raise

    async def read_events(
        self,
        exchange: str,
        symbol: str,
        event_type: str,
        start_time: int,
        end_time: int,
        limit: int = 10000,
    ) -> List[Dict[str, Any]]:
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
                    "event_type": event_type,
                    "start_time": start_time,
                    "end_time": end_time,
                    "limit": limit,
                }
            )

            import json
            events = []
            for row in rows:
                events.append({
                    "event_id": row[0],
                    "event_type": row[1],
                    "exchange": row[2],
                    "symbol": row[3],
                    "timestamp": row[4],
                    "sequence": row[5],
                    "partition": row[6],
                    "data": json.loads(row[7]) if row[7] else {},
                    "created_at": row[8],
                })
            return events
        except Exception as e:
            logger.error(f"Failed to read events: {e}")
            return []

    async def get_latest_timestamp(
        self,
        exchange: str,
        symbol: str,
        event_type: str,
    ) -> Optional[int]:
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
                    "event_type": event_type,
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
        event_type: str,
        start_time: int,
        end_time: int,
    ) -> int:
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
                    "event_type": event_type,
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

    async def save_checkpoint(self, checkpoint: Dict[str, Any]):
        try:
            await self.clickhouse.execute(
                """
                INSERT INTO replay_checkpoints (
                    checkpoint_id, replay_id, exchange, symbol, timeframe,
                    last_timestamp, last_sequence, processed_count,
                    created_at, metadata
                ) VALUES
                """,
                [checkpoint]
            )
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")

    async def load_checkpoint(
        self,
        replay_id: str,
        exchange: str,
        symbol: str,
        timeframe: str,
    ) -> Optional[Dict[str, Any]]:
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
                return {
                    "checkpoint_id": rows[0][0],
                    "replay_id": rows[0][1],
                    "exchange": rows[0][2],
                    "symbol": rows[0][3],
                    "timeframe": rows[0][4],
                    "last_timestamp": rows[0][5],
                    "last_sequence": rows[0][6],
                    "processed_count": rows[0][7],
                    "created_at": rows[0][8],
                    "metadata": rows[0][9] if len(rows[0]) > 9 else {},
                }
            return None
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return None

    async def delete_events(
        self,
        exchange: str,
        symbol: str,
        event_type: str,
        before_time: int,
    ) -> int:
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
                    "event_type": event_type,
                    "before_time": before_time,
                }
            )
            return 0
        except Exception as e:
            logger.error(f"Failed to delete events: {e}")
            return 0


_event_store_repo: Optional[EventStoreRepository] = None


async def get_event_store_repository() -> EventStoreRepository:
    global _event_store_repo
    if _event_store_repo is None:
        _event_store_repo = EventStoreRepository()
        await _event_store_repo.initialize()
    return _event_store_repo
