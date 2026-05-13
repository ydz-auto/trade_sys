"""
Time Travel Engine - 时间旅行引擎
跳转到任意时间点查看系统状态
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from infrastructure.logging import get_logger

logger = get_logger("infrastructure.replay.time_travel")


@dataclass
class SystemSnapshot:
    """系统快照"""

    snapshot_id: str
    timestamp: int
    label: str
    positions: Dict[str, Dict]
    orders: Dict[str, Dict]
    signals: List[Dict]
    portfolio_state: Dict
    strategy_states: Dict[str, Dict]
    risk_state: Dict
    created_at: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "timestamp": self.timestamp,
            "label": self.label,
            "positions": self.positions,
            "orders": self.orders,
            "signals": self.signals,
            "portfolio_state": self.portfolio_state,
            "strategy_states": self.strategy_states,
            "risk_state": self.risk_state,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SystemSnapshot":
        return cls(
            snapshot_id=data["snapshot_id"],
            timestamp=data["timestamp"],
            label=data.get("label", ""),
            positions=data.get("positions", {}),
            orders=data.get("orders", {}),
            signals=data.get("signals", []),
            portfolio_state=data.get("portfolio_state", {}),
            strategy_states=data.get("strategy_states", {}),
            risk_state=data.get("risk_state", {}),
            created_at=data.get("created_at", 0),
        )


class TimeTravelEngine:
    """时间旅行引擎

    能力：
    1. 跳转到任意时间点
    2. 重建系统状态
    3. 前进/后退
    4. 状态快照
    """

    def __init__(self, event_store=None, clickhouse_manager=None):
        self.event_store = event_store
        self.clickhouse_manager = clickhouse_manager
        self._snapshots: Dict[str, SystemSnapshot] = {}
        self._current_time: Optional[int] = None
        self._timeline_cache: Dict[str, List[Dict]] = {}

    async def travel_to(self, timestamp: int) -> SystemSnapshot:
        logger.info(f"Traveling to timestamp: {timestamp}")
        snapshot = await self._rebuild_state_at(timestamp)
        self._current_time = timestamp
        return snapshot

    async def forward(self, delta_ms: int) -> SystemSnapshot:
        if self._current_time is None:
            raise ValueError("No current time set, call travel_to first")
        target_time = self._current_time + delta_ms
        logger.info(f"Forwarding {delta_ms}ms to timestamp: {target_time}")
        snapshot = await self._rebuild_state_at(target_time)
        self._current_time = target_time
        return snapshot

    async def backward(self, delta_ms: int) -> SystemSnapshot:
        if self._current_time is None:
            raise ValueError("No current time set, call travel_to first")
        target_time = self._current_time - delta_ms
        if target_time < 0:
            raise ValueError("Cannot travel before epoch")
        logger.info(f"Backwarding {delta_ms}ms to timestamp: {target_time}")
        snapshot = await self._rebuild_state_at(target_time)
        self._current_time = target_time
        return snapshot

    async def get_state_at(self, timestamp: int) -> SystemSnapshot:
        snapshot = await self._rebuild_state_at(timestamp)
        return snapshot

    async def take_snapshot(self, label: str = "") -> SystemSnapshot:
        if self._current_time is None:
            raise ValueError("No current time set, call travel_to first")

        snapshot_id = f"snap_{uuid.uuid4().hex[:12]}"
        snapshot = SystemSnapshot(
            snapshot_id=snapshot_id,
            timestamp=self._current_time,
            label=label,
            positions={},
            orders={},
            signals=[],
            portfolio_state={},
            strategy_states={},
            risk_state={},
            created_at=int(datetime.now().timestamp() * 1000),
        )

        if self._current_time is not None:
            rebuilt = await self._rebuild_state_at(self._current_time)
            snapshot.positions = rebuilt.positions
            snapshot.orders = rebuilt.orders
            snapshot.signals = rebuilt.signals
            snapshot.portfolio_state = rebuilt.portfolio_state
            snapshot.strategy_states = rebuilt.strategy_states
            snapshot.risk_state = rebuilt.risk_state

        self._snapshots[snapshot_id] = snapshot
        logger.info(f"Taken snapshot: {snapshot_id} at timestamp: {self._current_time}")
        return snapshot

    async def restore_snapshot(self, snapshot_id: str) -> SystemSnapshot:
        snapshot = self._snapshots.get(snapshot_id)
        if snapshot is None:
            raise ValueError(f"Snapshot not found: {snapshot_id}")
        self._current_time = snapshot.timestamp
        logger.info(f"Restored snapshot: {snapshot_id} at timestamp: {snapshot.timestamp}")
        return snapshot

    async def list_snapshots(self) -> List[SystemSnapshot]:
        snapshots = sorted(
            self._snapshots.values(),
            key=lambda s: s.timestamp,
        )
        return snapshots

    async def get_event_timeline(
        self,
        start_time: int,
        end_time: int,
        symbol: Optional[str] = None,
    ) -> List[Dict]:
        cache_key = f"{start_time}_{end_time}_{symbol or 'all'}"
        if cache_key in self._timeline_cache:
            return self._timeline_cache[cache_key]

        timeline: List[Dict] = []

        if self.event_store is not None:
            try:
                from shared.replay.models import EventType

                for event_type in EventType:
                    events = await self.event_store.read_events(
                        exchange="",
                        symbol=symbol or "",
                        event_type=event_type,
                        start_time=start_time,
                        end_time=end_time,
                    )
                    for event in events:
                        if symbol and event.symbol != symbol:
                            continue
                        timeline.append(event.to_dict())
            except Exception as e:
                logger.error(f"Failed to get event timeline: {e}")

        timeline.sort(key=lambda x: x.get("timestamp", 0))
        self._timeline_cache[cache_key] = timeline
        return timeline

    async def _rebuild_state_at(self, timestamp: int) -> SystemSnapshot:
        positions: Dict[str, Dict] = {}
        orders: Dict[str, Dict] = {}
        signals: List[Dict] = []
        portfolio_state: Dict[str, Any] = {
            "total_value": 0.0,
            "unrealized_pnl": 0.0,
            "realized_pnl": 0.0,
        }
        strategy_states: Dict[str, Dict] = {}
        risk_state: Dict[str, Any] = {
            "risk_level": "low",
            "max_drawdown": 0.0,
            "exposure": 0.0,
        }

        if self.event_store is not None:
            try:
                from shared.replay.models import EventType

                for event_type in [EventType.SIGNAL, EventType.ORDER]:
                    events = await self.event_store.read_events(
                        exchange="",
                        symbol="",
                        event_type=event_type,
                        start_time=0,
                        end_time=timestamp,
                        limit=50000,
                    )
                    for event in events:
                        if event.event_type == EventType.SIGNAL:
                            signals.append(event.data)
                        elif event.event_type == EventType.ORDER:
                            orders[event.event_id] = event.data
            except Exception as e:
                logger.error(f"Failed to rebuild state: {e}")

        snapshot = SystemSnapshot(
            snapshot_id=f"state_{timestamp}",
            timestamp=timestamp,
            label="",
            positions=positions,
            orders=orders,
            signals=signals[-100:],
            portfolio_state=portfolio_state,
            strategy_states=strategy_states,
            risk_state=risk_state,
            created_at=int(datetime.now().timestamp() * 1000),
        )
        return snapshot

    async def delete_snapshot(self, snapshot_id: str) -> bool:
        if snapshot_id in self._snapshots:
            del self._snapshots[snapshot_id]
            logger.info(f"Deleted snapshot: {snapshot_id}")
            return True
        return False

    async def clear_timeline_cache(self) -> None:
        self._timeline_cache.clear()
        logger.info("Cleared timeline cache")
