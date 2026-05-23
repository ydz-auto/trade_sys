import asyncio
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any, AsyncIterator

from infrastructure.logging import get_logger
from infrastructure.messaging.schema.base_event import BaseEvent
from infrastructure.messaging.serializer import EventSerializer
from infrastructure.runtime_clock import now_ms

logger = get_logger("infrastructure.messaging.event_journal")


EVENT_JOURNAL_SCHEMA = {
    "event_journal": """
        CREATE TABLE IF NOT EXISTS event_journal (
            event_id String,
            trace_id String,
            parent_event_id Nullable(String),
            schema_version String,
            event_type String,
            category String,
            source String,
            symbol Nullable(String),
            event_time_ms Int64,
            ingest_time_ms Int64,
            process_time_ms Int64,
            clock_mode String,
            metadata String,
            payload String,
            created_at Int64
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(fromUnixTimestamp64Milli(event_time_ms))
        ORDER BY (event_type, symbol, event_time_ms, event_id)
    """,
}


class ClickHouseJournalBackend:
    def __init__(self):
        self._client = None
        self._initialized = False

    async def initialize(self) -> bool:
        if self._initialized:
            return True

        try:
            from infrastructure.database.clickhouse import get_clickhouse_manager
            manager = get_clickhouse_manager()
            await manager.connect()
            self._client = manager

            await self._ensure_table()
            self._initialized = True
            logger.info("ClickHouseJournalBackend initialized")
            return True
        except Exception as e:
            logger.warning(f"ClickHouse journal backend init failed: {e}")
            return False

    async def _ensure_table(self) -> None:
        if self._client is None:
            return
        try:
            schema_sql = EVENT_JOURNAL_SCHEMA["event_journal"]
            await self._client.execute(schema_sql)
        except Exception as e:
            logger.warning(f"Event journal table creation warning: {e}")

    async def append(self, event: BaseEvent) -> bool:
        if not self._initialized or self._client is None:
            return False

        try:
            row = self._event_to_row(event)
            await self._client.insert("event_journal", [row])
            return True
        except Exception as e:
            logger.error(f"Failed to append event to ClickHouse: {e}")
            return False

    async def append_batch(self, events: List[BaseEvent]) -> int:
        if not self._initialized or self._client is None:
            return 0
        if not events:
            return 0

        try:
            rows = [self._event_to_row(e) for e in events]
            await self._client.insert("event_journal", rows)
            return len(events)
        except Exception as e:
            logger.error(f"Failed to append batch to ClickHouse: {e}")
            return 0

    async def query(
        self,
        start_time_ms: Optional[int] = None,
        end_time_ms: Optional[int] = None,
        event_type: Optional[str] = None,
        symbol: Optional[str] = None,
        trace_id: Optional[str] = None,
        limit: int = 1000,
    ) -> List[BaseEvent]:
        if not self._initialized or self._client is None:
            return []

        try:
            conditions = []
            params: Dict[str, Any] = {"limit": limit}

            if start_time_ms is not None:
                conditions.append("event_time_ms >= %(start_time_ms)s")
                params["start_time_ms"] = start_time_ms
            if end_time_ms is not None:
                conditions.append("event_time_ms < %(end_time_ms)s")
                params["end_time_ms"] = end_time_ms
            if event_type is not None:
                conditions.append("event_type = %(event_type)s")
                params["event_type"] = event_type
            if symbol is not None:
                conditions.append("symbol = %(symbol)s")
                params["symbol"] = symbol
            if trace_id is not None:
                conditions.append("trace_id = %(trace_id)s")
                params["trace_id"] = trace_id

            where_clause = ""
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)

            query = f"""
                SELECT payload FROM event_journal
                {where_clause}
                ORDER BY event_time_ms, event_id
                LIMIT %(limit)s
            """

            rows = await self._client.fetch(query, params)
            events = []
            for row in rows:
                payload_str = row.get("payload") if isinstance(row, dict) else row[0]
                if payload_str:
                    try:
                        data = json.loads(payload_str) if isinstance(payload_str, str) else payload_str
                        from infrastructure.messaging.event_registry import parse_event
                        events.append(parse_event(data))
                    except Exception as e:
                        logger.warning(f"Failed to parse journal event: {e}")
            return events
        except Exception as e:
            logger.error(f"Failed to query event journal: {e}")
            return []

    @staticmethod
    def _event_to_row(event: BaseEvent) -> Dict[str, Any]:
        metadata_dict = dict(event.metadata) if event.metadata else {}
        return {
            "event_id": event.event_id,
            "trace_id": event.trace_id,
            "parent_event_id": event.parent_event_id,
            "schema_version": event.schema_version,
            "event_type": event.event_type,
            "category": event.category,
            "source": event.source,
            "symbol": event.symbol,
            "event_time_ms": event.event_time_ms,
            "ingest_time_ms": event.ingest_time_ms,
            "process_time_ms": event.process_time_ms,
            "clock_mode": event.clock_mode,
            "metadata": json.dumps(metadata_dict, default=str),
            "payload": event.to_json(),
            "created_at": now_ms(),
        }


class FileJournalBackend:
    def __init__(self, journal_dir: str = ""):
        if not journal_dir:
            data_dir = os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data"))
            journal_dir = os.path.join(data_dir, "event_journal")
        self._journal_dir = journal_dir
        self._initialized = False
        self._write_lock = asyncio.Lock()

    async def initialize(self) -> bool:
        if self._initialized:
            return True

        try:
            os.makedirs(self._journal_dir, exist_ok=True)
            self._initialized = True
            logger.info(f"FileJournalBackend initialized: {self._journal_dir}")
            return True
        except Exception as e:
            logger.warning(f"File journal backend init failed: {e}")
            return False

    async def append(self, event: BaseEvent) -> bool:
        if not self._initialized:
            return False

        try:
            line = event.to_json()
            date_str = datetime.utcfromtimestamp(event.event_time_ms / 1000).strftime("%Y-%m-%d")
            file_path = os.path.join(self._journal_dir, f"{date_str}.journal")

            async with self._write_lock:
                with open(file_path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            return True
        except Exception as e:
            logger.error(f"Failed to append event to file: {e}")
            return False

    async def append_batch(self, events: List[BaseEvent]) -> int:
        if not self._initialized or not events:
            return 0

        count = 0
        for event in events:
            if await self.append(event):
                count += 1
        return count

    async def query(
        self,
        start_time_ms: Optional[int] = None,
        end_time_ms: Optional[int] = None,
        event_type: Optional[str] = None,
        symbol: Optional[str] = None,
        trace_id: Optional[str] = None,
        limit: int = 1000,
    ) -> List[BaseEvent]:
        if not self._initialized:
            return []

        events: List[BaseEvent] = []

        try:
            files = sorted(
                f for f in os.listdir(self._journal_dir)
                if f.endswith(".journal")
            )

            for filename in files:
                if len(events) >= limit:
                    break

                date_str = filename.replace(".journal", "")
                try:
                    file_date = datetime.strptime(date_str, "%Y-%m-%d")
                    file_start_ms = int(file_date.timestamp() * 1000)
                    file_end_ms = file_start_ms + 86400000

                    if start_time_ms and file_end_ms < start_time_ms:
                        continue
                    if end_time_ms and file_start_ms > end_time_ms:
                        continue
                except ValueError:
                    continue

                file_path = os.path.join(self._journal_dir, filename)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        for line in f:
                            if len(events) >= limit:
                                break
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                data = json.loads(line)
                                if not self._matches_filter(data, start_time_ms, end_time_ms, event_type, symbol, trace_id):
                                    continue
                                from infrastructure.messaging.event_registry import parse_event
                                events.append(parse_event(data))
                            except Exception:
                                continue
                except Exception as e:
                    logger.warning(f"Failed to read journal file {filename}: {e}")

            return events
        except Exception as e:
            logger.error(f"Failed to query file journal: {e}")
            return []

    @staticmethod
    def _matches_filter(
        data: Dict[str, Any],
        start_time_ms: Optional[int],
        end_time_ms: Optional[int],
        event_type: Optional[str],
        symbol: Optional[str],
        trace_id: Optional[str],
    ) -> bool:
        if start_time_ms and data.get("event_time_ms", 0) < start_time_ms:
            return False
        if end_time_ms and data.get("event_time_ms", 0) >= end_time_ms:
            return False
        if event_type and data.get("event_type") != event_type:
            return False
        if symbol and data.get("symbol") != symbol:
            return False
        if trace_id and data.get("trace_id") != trace_id:
            return False
        return True


class EventJournal:
    def __init__(self, backend: str = "auto", journal_dir: str = ""):
        self._backend_name = backend
        self._journal_dir = journal_dir
        self._clickhouse_backend: Optional[ClickHouseJournalBackend] = None
        self._file_backend: Optional[FileJournalBackend] = None
        self._active_backend: Optional[str] = None
        self._initialized = False

        self._pending: List[BaseEvent] = []
        self._pending_lock = asyncio.Lock()
        self._batch_size = 50
        self._flush_interval_seconds = 2.0
        self._flush_task: Optional[asyncio.Task] = None

        self._stats = {
            "total_appended": 0,
            "total_flushed": 0,
            "total_failed": 0,
        }

    async def initialize(self) -> bool:
        if self._initialized:
            return True

        if self._backend_name in ("auto", "clickhouse"):
            ch = ClickHouseJournalBackend()
            if await ch.initialize():
                self._clickhouse_backend = ch
                self._active_backend = "clickhouse"
                logger.info("EventJournal using ClickHouse backend")

        if self._active_backend is None and self._backend_name in ("auto", "file"):
            fb = FileJournalBackend(self._journal_dir)
            if await fb.initialize():
                self._file_backend = fb
                self._active_backend = "file"
                logger.info("EventJournal using file backend")

        if self._active_backend is None:
            logger.error("No journal backend available")
            return False

        self._flush_task = asyncio.create_task(self._periodic_flush())
        self._initialized = True
        return True

    async def stop(self) -> None:
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
            self._flush_task = None

        await self._flush_pending()

        if self._clickhouse_backend:
            self._clickhouse_backend = None
        if self._file_backend:
            self._file_backend = None

        self._initialized = False
        logger.info(f"EventJournal stopped. Stats: {self._stats}")

    async def append(self, event: BaseEvent) -> bool:
        if not self._initialized:
            return False

        async with self._pending_lock:
            self._pending.append(event)
            self._stats["total_appended"] += 1

            if len(self._pending) >= self._batch_size:
                await self._flush_pending()

        return True

    async def query(
        self,
        start_time_ms: Optional[int] = None,
        end_time_ms: Optional[int] = None,
        event_type: Optional[str] = None,
        symbol: Optional[str] = None,
        trace_id: Optional[str] = None,
        limit: int = 1000,
    ) -> List[BaseEvent]:
        await self._flush_pending()

        if self._active_backend == "clickhouse" and self._clickhouse_backend:
            return await self._clickhouse_backend.query(
                start_time_ms, end_time_ms, event_type, symbol, trace_id, limit
            )
        if self._file_backend:
            return await self._file_backend.query(
                start_time_ms, end_time_ms, event_type, symbol, trace_id, limit
            )
        return []

    async def replay(
        self,
        start_time_ms: int,
        end_time_ms: int,
        event_type: Optional[str] = None,
        symbol: Optional[str] = None,
        batch_size: int = 1000,
    ) -> AsyncIterator[List[BaseEvent]]:
        current = start_time_ms
        while current < end_time_ms:
            events = await self.query(
                start_time_ms=current,
                end_time_ms=end_time_ms,
                event_type=event_type,
                symbol=symbol,
                limit=batch_size,
            )
            if not events:
                break
            yield events
            last_time = events[-1].event_time_ms
            if last_time <= current:
                current = last_time + 1
            else:
                current = last_time

    def get_stats(self) -> Dict[str, Any]:
        return {
            "backend": self._active_backend,
            "pending_count": len(self._pending),
            "stats": self._stats.copy(),
        }

    async def _flush_pending(self) -> None:
        async with self._pending_lock:
            if not self._pending:
                return
            batch = self._pending.copy()
            self._pending.clear()

        count = 0
        if self._active_backend == "clickhouse" and self._clickhouse_backend:
            count = await self._clickhouse_backend.append_batch(batch)
        elif self._file_backend:
            count = await self._file_backend.append_batch(batch)

        if count > 0:
            self._stats["total_flushed"] += count
        else:
            self._stats["total_failed"] += len(batch)
            async with self._pending_lock:
                self._pending.extend(batch)

    async def _periodic_flush(self) -> None:
        while True:
            try:
                await asyncio.sleep(self._flush_interval_seconds)
                await self._flush_pending()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Journal flush error: {e}")


_journal: Optional[EventJournal] = None


async def get_event_journal() -> EventJournal:
    global _journal
    if _journal is None:
        _journal = EventJournal()
        await _journal.initialize()
    return _journal


async def stop_event_journal() -> None:
    global _journal
    if _journal is not None:
        await _journal.stop()
        _journal = None
