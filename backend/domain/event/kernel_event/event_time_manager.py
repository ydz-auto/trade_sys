"""
Event Time Semantics - 事件时间语义

核心问题：
当前系统只有 feature_timestamp，没有区分：
- exchange_time: 交易所时间（事件发生时间）
- receive_time: 本地接收时间
- available_at: 可用时间（考虑延迟）

这导致 Replay 和 Live Runtime 的时间语义不一致。

解决方案：
1. 定义 EventTimeRecord 记录完整时间语义
2. 在 Replay 中模拟网络延迟
3. 在 Live 中记录真实延迟
4. 统一特征可用性判断
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import json

from infrastructure.logging import get_logger

logger = get_logger("runtime.kernel.event.event_time_manager")


from domain.event.time_types import EventSource, EventTimeRecord, EventTimeConfig


class EventTimeManager:

    def __init__(self, config: Optional[EventTimeConfig] = None):
        self.config = config or EventTimeConfig()

        self._events: Dict[str, EventTimeRecord] = {}
        self._time_index: Dict[str, List[int]] = {}

        self._delay_stats: Dict[str, List[int]] = {
            "network_delay": [],
            "processing_delay": [],
            "total_delay": [],
        }

    def record_event(
        self,
        event_id: str,
        event_type: str,
        exchange_time: int,
        receive_time: Optional[int] = None,
        source: EventSource = EventSource.EXCHANGE,
        network_delay_ms: Optional[int] = None,
        processing_delay_ms: Optional[int] = None,
        symbol: str = "",
        exchange: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> EventTimeRecord:
        if receive_time is None:
            receive_time = int(datetime.utcnow().timestamp() * 1000)

        if network_delay_ms is None:
            network_delay_ms = self.config.default_network_delay_ms

        if processing_delay_ms is None:
            processing_delay_ms = self.config.default_processing_delay_ms

        if source == EventSource.REPLAY and self.config.simulate_delay_in_replay:
            receive_time = exchange_time + network_delay_ms

        available_at = receive_time + processing_delay_ms

        record = EventTimeRecord(
            event_id=event_id,
            event_type=event_type,
            exchange_time=exchange_time,
            receive_time=receive_time,
            available_at=available_at,
            source=source,
            network_delay_ms=network_delay_ms,
            processing_delay_ms=processing_delay_ms,
            symbol=symbol,
            exchange=exchange,
            metadata=metadata or {},
        )

        self._events[event_id] = record

        key = f"{symbol}_{event_type}"
        if key not in self._time_index:
            self._time_index[key] = []
        self._time_index[key].append(exchange_time)

        self._delay_stats["network_delay"].append(network_delay_ms)
        self._delay_stats["processing_delay"].append(processing_delay_ms)
        self._delay_stats["total_delay"].append(record.get_total_delay_ms())

        return record

    def get_event(self, event_id: str) -> Optional[EventTimeRecord]:
        return self._events.get(event_id)

    def get_available_time(
        self,
        exchange_time: int,
        source: EventSource = EventSource.EXCHANGE,
    ) -> int:
        if source == EventSource.REPLAY and self.config.simulate_delay_in_replay:
            receive_time = exchange_time + self.config.default_network_delay_ms
        else:
            receive_time = int(datetime.utcnow().timestamp() * 1000)

        return receive_time + self.config.default_processing_delay_ms

    def check_event_availability(
        self,
        event_id: str,
        query_time: int,
    ) -> Tuple[bool, Optional[EventTimeRecord]]:
        record = self._events.get(event_id)
        if record is None:
            return False, None

        return record.is_available_at(query_time), record

    def get_events_in_range(
        self,
        start_time: int,
        end_time: int,
        symbol: Optional[str] = None,
        event_type: Optional[str] = None,
        use_exchange_time: bool = True,
    ) -> List[EventTimeRecord]:
        results = []

        for event in self._events.values():
            if symbol and event.symbol != symbol:
                continue
            if event_type and event.event_type != event_type:
                continue

            time_to_check = event.exchange_time if use_exchange_time else event.available_at

            if start_time <= time_to_check <= end_time:
                results.append(event)

        return sorted(results, key=lambda e: e.exchange_time)

    def get_available_events(
        self,
        query_time: int,
        symbol: Optional[str] = None,
        event_type: Optional[str] = None,
    ) -> List[EventTimeRecord]:
        results = []

        for event in self._events.values():
            if symbol and event.symbol != symbol:
                continue
            if event_type and event.event_type != event_type:
                continue

            if event.is_available_at(query_time):
                results.append(event)

        return sorted(results, key=lambda e: e.available_at)

    def get_delay_stats(self) -> Dict[str, Any]:
        import numpy as np

        stats = {}

        for name, delays in self._delay_stats.items():
            if delays:
                stats[name] = {
                    "count": len(delays),
                    "mean_ms": float(np.mean(delays)),
                    "median_ms": float(np.median(delays)),
                    "max_ms": float(np.max(delays)),
                    "min_ms": float(np.min(delays)),
                    "p95_ms": float(np.percentile(delays, 95)) if len(delays) >= 20 else float(np.max(delays)),
                }

        return stats

    def validate_time_consistency(self) -> List[Dict[str, Any]]:
        issues = []

        for event_id, event in self._events.items():
            if event.receive_time < event.exchange_time:
                issues.append({
                    "event_id": event_id,
                    "type": "receive_before_exchange",
                    "message": f"Receive time {event.receive_time} is before exchange time {event.exchange_time}",
                })

            total_delay = event.get_total_delay_ms()
            if total_delay > self.config.max_acceptable_delay_ms:
                issues.append({
                    "event_id": event_id,
                    "type": "excessive_delay",
                    "message": f"Total delay {total_delay}ms exceeds max acceptable {self.config.max_acceptable_delay_ms}ms",
                })

        return issues

    def clear(self):
        self._events.clear()
        self._time_index.clear()
        for key in self._delay_stats:
            self._delay_stats[key] = []


_manager_instance: Optional[EventTimeManager] = None


def get_event_time_manager(config: Optional[EventTimeConfig] = None) -> EventTimeManager:
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = EventTimeManager(config)
    return _manager_instance


def record_event_time(
    event_id: str,
    event_type: str,
    exchange_time: int,
    **kwargs,
) -> EventTimeRecord:
    manager = get_event_time_manager()
    return manager.record_event(
        event_id=event_id,
        event_type=event_type,
        exchange_time=exchange_time,
        **kwargs,
    )
