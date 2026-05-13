"""
Strategy Rewind Engine - 策略回溯引擎
回溯策略状态到历史任意点
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from infrastructure.logging import get_logger

logger = get_logger("infrastructure.replay.strategy_rewind")


@dataclass
class StrategyState:
    """策略状态"""

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
    """决策上下文"""

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
    """策略状态差异"""

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
    """决策审计条目"""

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


class StrategyRewindEngine:
    """策略回溯引擎

    能力：
    1. 回溯策略状态到历史任意点
    2. 查看策略在特定时间的决策上下文
    3. 对比不同时间点的策略状态
    4. 策略决策审计
    """

    def __init__(self, event_store=None, clickhouse_manager=None):
        self.event_store = event_store
        self.clickhouse_manager = clickhouse_manager
        self._strategy_states: Dict[str, Dict[int, StrategyState]] = {}
        self._decision_contexts: Dict[str, DecisionContext] = {}

    async def rewind_to(self, strategy_id: str, timestamp: int) -> StrategyState:
        logger.info(f"Rewinding strategy {strategy_id} to timestamp: {timestamp}")

        states = self._strategy_states.get(strategy_id, {})
        if states:
            candidates = [t for t in states.keys() if t <= timestamp]
            if candidates:
                closest_ts = max(candidates)
                return states[closest_ts]

        state = await self._rebuild_strategy_state(strategy_id, timestamp)

        if strategy_id not in self._strategy_states:
            self._strategy_states[strategy_id] = {}
        self._strategy_states[strategy_id][timestamp] = state

        logger.info(
            f"Rewound strategy {strategy_id} to timestamp: {timestamp}, "
            f"decisions={len(state.decisions_made)}, signals={len(state.signals_received)}"
        )
        return state

    async def get_decision_context(
        self, strategy_id: str, decision_id: str
    ) -> DecisionContext:
        if decision_id in self._decision_contexts:
            return self._decision_contexts[decision_id]

        decision_data = await self._find_decision(decision_id)
        if decision_data is None:
            raise ValueError(f"Decision not found: {decision_id}")

        strategy_state = await self.rewind_to(
            strategy_id, decision_data["timestamp"]
        )

        context = DecisionContext(
            decision_id=decision_id,
            strategy_id=strategy_id,
            timestamp=decision_data["timestamp"],
            action=decision_data.get("action", "HOLD"),
            symbol=decision_data.get("symbol", ""),
            input_signals=decision_data.get("input_signals", []),
            market_state=decision_data.get("market_state", {}),
            strategy_state=strategy_state,
            risk_state=decision_data.get("risk_state", {}),
            reasoning=decision_data.get("reasoning", ""),
        )

        self._decision_contexts[decision_id] = context
        logger.info(f"Retrieved decision context: {decision_id}")
        return context

    async def compare_states(
        self, strategy_id: str, timestamp_a: int, timestamp_b: int
    ) -> StrategyStateDiff:
        state_a = await self.rewind_to(strategy_id, timestamp_a)
        state_b = await self.rewind_to(strategy_id, timestamp_b)

        position_changes = self._compute_position_diff(
            state_a.positions, state_b.positions
        )
        signal_changes = self._compute_signal_diff(
            state_a.signals_received, state_b.signals_received
        )
        parameter_changes = self._compute_parameter_diff(
            state_a.parameters, state_b.parameters
        )
        performance_delta = self._compute_performance_delta(
            state_a.performance, state_b.performance
        )

        diff = StrategyStateDiff(
            strategy_id=strategy_id,
            timestamp_a=timestamp_a,
            timestamp_b=timestamp_b,
            position_changes=position_changes,
            signal_changes=signal_changes,
            parameter_changes=parameter_changes,
            performance_delta=performance_delta,
        )

        logger.info(
            f"Compared strategy {strategy_id} states: "
            f"{timestamp_a} vs {timestamp_b}, "
            f"position_changes={len(position_changes)}, "
            f"parameter_changes={len(parameter_changes)}"
        )
        return diff

    async def get_decision_audit_trail(
        self, strategy_id: str, start_time: int, end_time: int
    ) -> List[DecisionAuditEntry]:
        entries: List[DecisionAuditEntry] = []

        states = self._strategy_states.get(strategy_id, {})
        for ts, state in states.items():
            if start_time <= ts <= end_time:
                for decision in state.decisions_made:
                    entry = DecisionAuditEntry(
                        decision_id=decision.get("decision_id", str(uuid.uuid4())),
                        timestamp=ts,
                        action=decision.get("action", "HOLD"),
                        symbol=decision.get("symbol", ""),
                        confidence=decision.get("confidence", 0.0),
                        input_signals_count=decision.get("input_signals_count", 0),
                        risk_approved=decision.get("risk_approved", False),
                        outcome=decision.get("outcome"),
                        pnl=decision.get("pnl"),
                    )
                    entries.append(entry)

        if not entries and self.event_store is not None:
            entries = await self._load_audit_trail_from_store(
                strategy_id, start_time, end_time
            )

        entries.sort(key=lambda e: e.timestamp)
        logger.info(
            f"Decision audit trail for {strategy_id}: "
            f"{len(entries)} entries between {start_time} and {end_time}"
        )
        return entries

    async def save_strategy_state(
        self, strategy_id: str, state: Dict, timestamp: int
    ) -> None:
        strategy_state = StrategyState(
            strategy_id=strategy_id,
            timestamp=timestamp,
            positions=state.get("positions", {}),
            signals_received=state.get("signals_received", []),
            decisions_made=state.get("decisions_made", []),
            parameters=state.get("parameters", {}),
            performance=state.get("performance", {}),
            regime=state.get("regime", "unknown"),
            confidence=state.get("confidence", 0.0),
        )

        if strategy_id not in self._strategy_states:
            self._strategy_states[strategy_id] = {}
        self._strategy_states[strategy_id][timestamp] = strategy_state
        logger.info(
            f"Saved strategy state: {strategy_id} at timestamp: {timestamp}"
        )

    async def _rebuild_strategy_state(
        self, strategy_id: str, timestamp: int
    ) -> StrategyState:
        positions: Dict[str, Dict] = {}
        signals_received: List[Dict] = []
        decisions_made: List[Dict] = []
        parameters: Dict[str, Any] = {}
        performance: Dict[str, float] = {
            "total_pnl": 0.0,
            "win_rate": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
        }

        if self.event_store is not None:
            try:
                from shared.replay.models import EventType

                signal_events = await self.event_store.read_events(
                    exchange="",
                    symbol="",
                    event_type=EventType.SIGNAL,
                    start_time=0,
                    end_time=timestamp,
                    limit=10000,
                )
                for event in signal_events:
                    signals_received.append(event.data)

                order_events = await self.event_store.read_events(
                    exchange="",
                    symbol="",
                    event_type=EventType.ORDER,
                    start_time=0,
                    end_time=timestamp,
                    limit=10000,
                )
                for event in order_events:
                    decisions_made.append(event.data)
            except Exception as e:
                logger.error(f"Failed to rebuild strategy state: {e}")

        return StrategyState(
            strategy_id=strategy_id,
            timestamp=timestamp,
            positions=positions,
            signals_received=signals_received[-50:],
            decisions_made=decisions_made[-50:],
            parameters=parameters,
            performance=performance,
            regime="unknown",
            confidence=0.0,
        )

    async def _find_decision(self, decision_id: str) -> Optional[Dict]:
        for strategy_id, states in self._strategy_states.items():
            for ts, state in states.items():
                for decision in state.decisions_made:
                    if decision.get("decision_id") == decision_id:
                        return {
                            **decision,
                            "timestamp": ts,
                            "strategy_id": strategy_id,
                        }
        return None

    async def _load_audit_trail_from_store(
        self, strategy_id: str, start_time: int, end_time: int
    ) -> List[DecisionAuditEntry]:
        entries: List[DecisionAuditEntry] = []
        if self.event_store is None:
            return entries

        try:
            from shared.replay.models import EventType

            events = await self.event_store.read_events(
                exchange="",
                symbol="",
                event_type=EventType.ORDER,
                start_time=start_time,
                end_time=end_time,
                limit=50000,
            )
            for event in events:
                data = event.data
                if data.get("strategy_id") != strategy_id:
                    continue
                entry = DecisionAuditEntry(
                    decision_id=data.get("decision_id", str(uuid.uuid4())),
                    timestamp=event.timestamp,
                    action=data.get("action", "HOLD"),
                    symbol=event.symbol,
                    confidence=data.get("confidence", 0.0),
                    input_signals_count=data.get("input_signals_count", 0),
                    risk_approved=data.get("risk_approved", False),
                    outcome=data.get("outcome"),
                    pnl=data.get("pnl"),
                )
                entries.append(entry)
        except Exception as e:
            logger.error(f"Failed to load audit trail from store: {e}")

        return entries

    def _compute_position_diff(
        self, positions_a: Dict, positions_b: Dict
    ) -> List[Dict]:
        changes: List[Dict] = []
        all_keys = set(positions_a.keys()) | set(positions_b.keys())
        for key in all_keys:
            pos_a = positions_a.get(key)
            pos_b = positions_b.get(key)
            if pos_a != pos_b:
                changes.append(
                    {
                        "symbol": key,
                        "before": pos_a,
                        "after": pos_b,
                    }
                )
        return changes

    def _compute_signal_diff(
        self, signals_a: List[Dict], signals_b: List[Dict]
    ) -> List[Dict]:
        changes: List[Dict] = []
        ids_a = {s.get("signal_id", s.get("signal_name", "")) for s in signals_a}
        ids_b = {s.get("signal_id", s.get("signal_name", "")) for s in signals_b}

        added = ids_b - ids_a
        removed = ids_a - ids_b

        for sig_id in added:
            for s in signals_b:
                if s.get("signal_id", s.get("signal_name", "")) == sig_id:
                    changes.append({"type": "added", "signal": s})
                    break

        for sig_id in removed:
            for s in signals_a:
                if s.get("signal_id", s.get("signal_name", "")) == sig_id:
                    changes.append({"type": "removed", "signal": s})
                    break

        return changes

    def _compute_parameter_diff(
        self, params_a: Dict, params_b: Dict
    ) -> Dict[str, Tuple[Any, Any]]:
        changes: Dict[str, Tuple[Any, Any]] = {}
        all_keys = set(params_a.keys()) | set(params_b.keys())
        for key in all_keys:
            val_a = params_a.get(key)
            val_b = params_b.get(key)
            if val_a != val_b:
                changes[key] = (val_a, val_b)
        return changes

    def _compute_performance_delta(
        self, perf_a: Dict[str, float], perf_b: Dict[str, float]
    ) -> Dict[str, float]:
        delta: Dict[str, float] = {}
        all_keys = set(perf_a.keys()) | set(perf_b.keys())
        for key in all_keys:
            val_a = perf_a.get(key, 0.0)
            val_b = perf_b.get(key, 0.0)
            delta[key] = val_b - val_a
        return delta
