from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum
import json

from domain.event.base_event import Timeframe, Exchange


class EventType(str, Enum):
    TRADE = "trade"
    CANDLE_1M = "candle_1m"
    CANDLE_5M = "candle_5m"
    CANDLE_15M = "candle_15m"
    CANDLE_1H = "candle_1h"
    CANDLE_4H = "candle_4h"
    CANDLE_1D = "candle_1d"
    TICKER = "ticker"
    ORDER_BOOK = "order_book"
    SIGNAL = "signal"
    ORDER = "order"


class ReplayStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RebuildStatus(str, Enum):
    PENDING = "pending"
    DETECTING = "detecting"
    REBUILDING = "rebuilding"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class EventRecord:
    event_id: str
    event_type: EventType
    exchange: str
    symbol: str
    timestamp: int
    data: Dict[str, Any]

    sequence: int = 0
    partition: int = 0

    created_at: int = field(default_factory=lambda: int(datetime.now().timestamp() * 1000))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "exchange": self.exchange,
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "data": self.data,
            "sequence": self.sequence,
            "partition": self.partition,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EventRecord":
        return cls(
            event_id=data["event_id"],
            event_type=EventType(data["event_type"]),
            exchange=data["exchange"],
            symbol=data["symbol"],
            timestamp=data["timestamp"],
            data=data["data"],
            sequence=data.get("sequence", 0),
            partition=data.get("partition", 0),
            created_at=data.get("created_at", 0),
        )


@dataclass
class ReplayCheckpoint:
    checkpoint_id: str
    replay_id: str

    exchange: str
    symbol: str
    timeframe: str

    last_timestamp: int
    last_sequence: int
    processed_count: int

    created_at: int = field(default_factory=lambda: int(datetime.now().timestamp() * 1000))

    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "replay_id": self.replay_id,
            "exchange": self.exchange,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "last_timestamp": self.last_timestamp,
            "last_sequence": self.last_sequence,
            "processed_count": self.processed_count,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReplayCheckpoint":
        return cls(
            checkpoint_id=data["checkpoint_id"],
            replay_id=data["replay_id"],
            exchange=data["exchange"],
            symbol=data["symbol"],
            timeframe=data["timeframe"],
            last_timestamp=data["last_timestamp"],
            last_sequence=data["last_sequence"],
            processed_count=data["processed_count"],
            created_at=data.get("created_at", 0),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ReplayTask:
    task_id: str
    exchange: str
    symbol: str
    timeframe: str

    start_time: int
    end_time: int

    speed: float = 1.0
    batch_size: int = 1000

    status: ReplayStatus = ReplayStatus.PENDING

    progress: float = 0.0
    processed_count: int = 0
    error_count: int = 0

    created_at: int = field(default_factory=lambda: int(datetime.now().timestamp() * 1000))
    started_at: Optional[int] = None
    completed_at: Optional[int] = None

    checkpoint: Optional[ReplayCheckpoint] = None
    error: Optional[str] = None

    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "exchange": self.exchange,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "speed": self.speed,
            "batch_size": self.batch_size,
            "status": self.status.value,
            "progress": self.progress,
            "processed_count": self.processed_count,
            "error_count": self.error_count,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "checkpoint": self.checkpoint.to_dict() if self.checkpoint else None,
            "error": self.error,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReplayTask":
        checkpoint = None
        if data.get("checkpoint"):
            checkpoint = ReplayCheckpoint.from_dict(data["checkpoint"])

        return cls(
            task_id=data["task_id"],
            exchange=data["exchange"],
            symbol=data["symbol"],
            timeframe=data["timeframe"],
            start_time=data["start_time"],
            end_time=data["end_time"],
            speed=data.get("speed", 1.0),
            batch_size=data.get("batch_size", 1000),
            status=ReplayStatus(data.get("status", "pending")),
            progress=data.get("progress", 0.0),
            processed_count=data.get("processed_count", 0),
            error_count=data.get("error_count", 0),
            created_at=data.get("created_at", 0),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            checkpoint=checkpoint,
            error=data.get("error"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class RebuildTask:
    task_id: str
    exchange: str
    symbol: str
    timeframe: str

    start_time: int
    end_time: int

    strategy: str = "rebuild"

    status: RebuildStatus = RebuildStatus.PENDING

    gaps_found: int = 0
    gaps_repaired: int = 0
    candles_rebuilt: int = 0

    created_at: int = field(default_factory=lambda: int(datetime.now().timestamp() * 1000))
    started_at: Optional[int] = None
    completed_at: Optional[int] = None

    error: Optional[str] = None

    gap_details: List[Dict[str, Any]] = field(default_factory=list)

    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "exchange": self.exchange,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "strategy": self.strategy,
            "status": self.status.value,
            "gaps_found": self.gaps_found,
            "gaps_repaired": self.gaps_repaired,
            "candles_rebuilt": self.candles_rebuilt,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "gap_details": self.gap_details,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RebuildTask":
        return cls(
            task_id=data["task_id"],
            exchange=data["exchange"],
            symbol=data["symbol"],
            timeframe=data["timeframe"],
            start_time=data["start_time"],
            end_time=data["end_time"],
            strategy=data.get("strategy", "rebuild"),
            status=RebuildStatus(data.get("status", "pending")),
            gaps_found=data.get("gaps_found", 0),
            gaps_repaired=data.get("gaps_repaired", 0),
            candles_rebuilt=data.get("candles_rebuilt", 0),
            created_at=data.get("created_at", 0),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            error=data.get("error"),
            gap_details=data.get("gap_details", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ReplayStats:
    total_tasks: int = 0
    running_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0

    total_events_processed: int = 0
    total_errors: int = 0

    avg_speed: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_tasks": self.total_tasks,
            "running_tasks": self.running_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "total_events_processed": self.total_events_processed,
            "total_errors": self.total_errors,
            "avg_speed": self.avg_speed,
        }


@dataclass
class RebuildStats:
    total_tasks: int = 0
    running_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0

    total_gaps_found: int = 0
    total_gaps_repaired: int = 0
    total_candles_rebuilt: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_tasks": self.total_tasks,
            "running_tasks": self.running_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "total_gaps_found": self.total_gaps_found,
            "total_gaps_repaired": self.total_gaps_repaired,
            "total_candles_rebuilt": self.total_candles_rebuilt,
        }
