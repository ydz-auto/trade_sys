"""
Runtime Timeline - Runtime 时间线

核心职责:
1. 记录 runtime 事件时间线
2. 支持 replay/debug
3. 事件回溯
"""
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import json

from domain.trading_mode import TradingMode
from runtimes.trading_mode_manager import get_trading_mode_manager
from infrastructure.logging import get_logger
from infrastructure.utilities.runtime_clock import now_ms

logger = get_logger("runtime.timeline")


class TimelineEventType(str, Enum):
    RUNTIME_START = "runtime_start"
    RUNTIME_STOP = "runtime_stop"
    RUNTIME_ERROR = "runtime_error"
    RUNTIME_RECOVER = "runtime_recover"
    SIGNAL_TRIGGERED = "signal_triggered"
    ORDER_CREATED = "order_created"
    ORDER_FILLED = "order_filled"
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    RISK_WARNING = "risk_warning"
    MODE_CHANGE = "mode_change"
    FEATURE_UPDATE = "feature_update"
    BEHAVIOUR_DETECTED = "behaviour_detected"


@dataclass
class TimelineEvent:
    event_id: str
    event_type: TimelineEventType
    timestamp: datetime
    runtime_id: Optional[str] = None
    symbol: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "runtime_id": self.runtime_id,
            "symbol": self.symbol,
            "data": self.data,
            "metadata": self.metadata,
        }


@dataclass
class TimelineSnapshot:
    snapshot_id: str
    timestamp: datetime
    events: List[TimelineEvent]
    mode: TradingMode
    duration_seconds: float


class RuntimeTimeline:
    _instance: Optional['RuntimeTimeline'] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, max_events: int = 100000):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._initialized = True
        self._mode_manager = get_trading_mode_manager()
        self._max_events = max_events
        
        self._events: List[TimelineEvent] = []
        self._event_index: Dict[str, TimelineEvent] = {}
        
        self._by_type: Dict[TimelineEventType, List[str]] = {et: [] for et in TimelineEventType}
        self._by_runtime: Dict[str, List[str]] = {}
        self._by_symbol: Dict[str, List[str]] = {}
        
        self._subscribers: List[Callable] = []
        
        self._snapshots: List[TimelineSnapshot] = []
        self._max_snapshots = 100
        
        self._event_counter = 0
        self._snapshot_counter = 0
        
        self._stats = {
            "total_events": 0,
            "events_by_type": {et.value: 0 for et in TimelineEventType},
        }
        
        logger.info("RuntimeTimeline initialized")

    def _generate_event_id(self) -> str:
        self._event_counter += 1
        return f"evt_{self._event_counter}_{datetime.fromtimestamp(now_ms() / 1000).strftime('%Y%m%d%H%M%S')}"

    def record(
        self,
        event_type: TimelineEventType,
        data: Optional[Dict[str, Any]] = None,
        runtime_id: Optional[str] = None,
        symbol: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TimelineEvent:
        event = TimelineEvent(
            event_id=self._generate_event_id(),
            event_type=event_type,
            timestamp=datetime.fromtimestamp(now_ms() / 1000),
            runtime_id=runtime_id,
            symbol=symbol,
            data=data or {},
            metadata=metadata or {},
        )
        
        self._events.append(event)
        self._event_index[event.event_id] = event
        
        self._by_type[event_type].append(event.event_id)
        
        if runtime_id:
            if runtime_id not in self._by_runtime:
                self._by_runtime[runtime_id] = []
            self._by_runtime[runtime_id].append(event.event_id)
        
        if symbol:
            if symbol not in self._by_symbol:
                self._by_symbol[symbol] = []
            self._by_symbol[symbol].append(event.event_id)
        
        self._stats["total_events"] += 1
        self._stats["events_by_type"][event_type.value] += 1
        
        if len(self._events) > self._max_events:
            removed = self._events.pop(0)
            self._event_index.pop(removed.event_id, None)
        
        self._notify_subscribers(event)
        
        return event

    def record_runtime_start(self, runtime_id: str, **kwargs) -> TimelineEvent:
        return self.record(TimelineEventType.RUNTIME_START, runtime_id=runtime_id, data=kwargs)

    def record_runtime_stop(self, runtime_id: str, **kwargs) -> TimelineEvent:
        return self.record(TimelineEventType.RUNTIME_STOP, runtime_id=runtime_id, data=kwargs)

    def record_runtime_error(self, runtime_id: str, error: str, **kwargs) -> TimelineEvent:
        return self.record(TimelineEventType.RUNTIME_ERROR, runtime_id=runtime_id, data={"error": error, **kwargs})

    def record_signal(self, symbol: str, signal_data: Dict[str, Any], **kwargs) -> TimelineEvent:
        return self.record(TimelineEventType.SIGNAL_TRIGGERED, symbol=symbol, data=signal_data, **kwargs)

    def record_order(self, symbol: str, order_data: Dict[str, Any], **kwargs) -> TimelineEvent:
        event_type = TimelineEventType.ORDER_CREATED if order_data.get("status") == "created" else TimelineEventType.ORDER_FILLED
        return self.record(event_type, symbol=symbol, data=order_data, **kwargs)

    def record_position(self, symbol: str, position_data: Dict[str, Any], **kwargs) -> TimelineEvent:
        event_type = TimelineEventType.POSITION_OPENED if position_data.get("action") == "open" else TimelineEventType.POSITION_CLOSED
        return self.record(event_type, symbol=symbol, data=position_data, **kwargs)

    def record_mode_change(self, from_mode: str, to_mode: str, **kwargs) -> TimelineEvent:
        return self.record(TimelineEventType.MODE_CHANGE, data={"from": from_mode, "to": to_mode, **kwargs})

    def get_event(self, event_id: str) -> Optional[TimelineEvent]:
        return self._event_index.get(event_id)

    def get_events(
        self,
        event_type: Optional[TimelineEventType] = None,
        runtime_id: Optional[str] = None,
        symbol: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[TimelineEvent]:
        events = self._events
        
        if event_type:
            event_ids = set(self._by_type[event_type])
            events = [e for e in events if e.event_id in event_ids]
        
        if runtime_id:
            event_ids = set(self._by_runtime.get(runtime_id, []))
            events = [e for e in events if e.event_id in event_ids]
        
        if symbol:
            event_ids = set(self._by_symbol.get(symbol, []))
            events = [e for e in events if e.event_id in event_ids]
        
        if start_time:
            events = [e for e in events if e.timestamp >= start_time]
        
        if end_time:
            events = [e for e in events if e.timestamp <= end_time]
        
        return events[-limit:]

    def get_recent(self, limit: int = 100) -> List[TimelineEvent]:
        return self._events[-limit:]

    def get_by_runtime(self, runtime_id: str, limit: int = 100) -> List[TimelineEvent]:
        event_ids = self._by_runtime.get(runtime_id, [])[-limit:]
        return [self._event_index[eid] for eid in event_ids if eid in self._event_index]

    def get_by_symbol(self, symbol: str, limit: int = 100) -> List[TimelineEvent]:
        event_ids = self._by_symbol.get(symbol, [])[-limit:]
        return [self._event_index[eid] for eid in event_ids if eid in self._event_index]

    def create_snapshot(self, duration_seconds: float = 3600) -> TimelineSnapshot:
        end_time = datetime.fromtimestamp(now_ms() / 1000)
        start_time = end_time - timedelta(seconds=duration_seconds)
        
        events = [e for e in self._events if e.timestamp >= start_time]
        
        self._snapshot_counter += 1
        snapshot = TimelineSnapshot(
            snapshot_id=f"snap_{self._snapshot_counter}",
            timestamp=datetime.fromtimestamp(now_ms() / 1000),
            events=events,
            mode=self._mode_manager.mode,
            duration_seconds=duration_seconds,
        )
        
        self._snapshots.append(snapshot)
        
        if len(self._snapshots) > self._max_snapshots:
            self._snapshots = self._snapshots[-self._max_snapshots:]
        
        logger.info(f"Created timeline snapshot: {snapshot.snapshot_id} ({len(events)} events)")
        
        return snapshot

    def get_snapshots(self, limit: int = 10) -> List[Dict[str, Any]]:
        return [
            {
                "snapshot_id": s.snapshot_id,
                "timestamp": s.timestamp.isoformat(),
                "mode": s.mode.value,
                "duration_seconds": s.duration_seconds,
                "event_count": len(s.events),
            }
            for s in self._snapshots[-limit:]
        ]

    def subscribe(self, callback: Callable) -> None:
        self._subscribers.append(callback)

    def _notify_subscribers(self, event: TimelineEvent) -> None:
        for callback in self._subscribers:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Timeline subscriber error: {e}")

    def export(self, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None) -> Dict[str, Any]:
        events = self.get_events(start_time=start_time, end_time=end_time, limit=self._max_events)
        
        return {
            "export_time": datetime.fromtimestamp(now_ms() / 1000).isoformat(),
            "mode": self._mode_manager.mode.value,
            "event_count": len(events),
            "events": [e.to_dict() for e in events],
        }

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_events": len(self._events),
            "max_events": self._max_events,
            "snapshots": len(self._snapshots),
            "stats": self._stats.copy(),
        }


def get_runtime_timeline() -> RuntimeTimeline:
    return RuntimeTimeline()


def record_event(event_type: TimelineEventType, **kwargs) -> TimelineEvent:
    timeline = get_runtime_timeline()
    return timeline.record(event_type, **kwargs)
