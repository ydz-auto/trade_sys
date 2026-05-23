"""
Low-level strategy rewind data primitives. High-level strategy state management belongs in runtime.replay_runtime.

Data structures only:
- StrategyState: 策略状态
- DecisionContext: 决策上下文
- StrategyStateDiff: 策略状态差异
- DecisionAuditEntry: 决策审计条目

State management and orchestration (rewind_to, compare_states, etc.) belong in runtime.replay_runtime.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class StrategyState:
    strategy_id: str
    timestamp: int
    positions: Dict[str, Dict]
    signals_received: List[Dict]
    decisions_made: List[Dict]
    parameters: Dict[str, Any]
    performance: Dict[str, float]
    regime: str
    confidence: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "timestamp": self.timestamp,
            "positions": self.positions,
            "signals_received": self.signals_received,
            "decisions_made": self.decisions_made,
            "parameters": self.parameters,
            "performance": self.performance,
            "regime": self.regime,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StrategyState":
        return cls(
            strategy_id=data["strategy_id"],
            timestamp=data["timestamp"],
            positions=data.get("positions", {}),
            signals_received=data.get("signals_received", []),
            decisions_made=data.get("decisions_made", []),
            parameters=data.get("parameters", {}),
            performance=data.get("performance", {}),
            regime=data.get("regime", "unknown"),
            confidence=data.get("confidence", 0.0),
        )


@dataclass
class DecisionContext:
    decision_id: str
    strategy_id: str
    timestamp: int
    action: str
    symbol: str
    input_signals: List[Dict]
    market_state: Dict
    strategy_state: StrategyState
    risk_state: Dict
    reasoning: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "strategy_id": self.strategy_id,
            "timestamp": self.timestamp,
            "action": self.action,
            "symbol": self.symbol,
            "input_signals": self.input_signals,
            "market_state": self.market_state,
            "strategy_state": self.strategy_state.to_dict(),
            "risk_state": self.risk_state,
            "reasoning": self.reasoning,
        }


@dataclass
class StrategyStateDiff:
    strategy_id: str
    timestamp_a: int
    timestamp_b: int
    position_changes: List[Dict]
    signal_changes: List[Dict]
    parameter_changes: Dict[str, Tuple[Any, Any]]
    performance_delta: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "timestamp_a": self.timestamp_a,
            "timestamp_b": self.timestamp_b,
            "position_changes": self.position_changes,
            "signal_changes": self.signal_changes,
            "parameter_changes": {
                k: [v[0], v[1]] for k, v in self.parameter_changes.items()
            },
            "performance_delta": self.performance_delta,
        }


@dataclass
class DecisionAuditEntry:
    decision_id: str
    timestamp: int
    action: str
    symbol: str
    confidence: float
    input_signals_count: int
    risk_approved: bool
    outcome: Optional[str]
    pnl: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "timestamp": self.timestamp,
            "action": self.action,
            "symbol": self.symbol,
            "confidence": self.confidence,
            "input_signals_count": self.input_signals_count,
            "risk_approved": self.risk_approved,
            "outcome": self.outcome,
            "pnl": self.pnl,
        }
