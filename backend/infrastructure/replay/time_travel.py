"""
Low-level time travel data primitives. High-level time travel orchestration belongs in runtime.replay_runtime.

Data structures only:
- SystemSnapshot: 系统快照数据结构

State management and orchestration (travel_to, forward, backward, etc.) belong in runtime.replay_runtime.
"""

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class SystemSnapshot:
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
