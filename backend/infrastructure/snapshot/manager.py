"""
Snapshot Recovery System - 快照恢复系统

提供完整的状态快照和恢复能力：
- Portfolio Snapshot
- Strategy Snapshot
- Execution Snapshot
- Risk Snapshot
- Full System Snapshot

支持：
- 定期自动快照
- 手动快照
- 快照恢复
- 快照验证
"""

import asyncio
import json
import hashlib
from typing import Dict, List, Optional, Any, Callable, Awaitable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import uuid

from infrastructure.logging import get_logger
from infrastructure.database import ClickHouseManager

logger = get_logger("infrastructure.snapshot.manager")


class SnapshotType(str, Enum):
    """快照类型"""
    FULL = "full"
    PORTFOLIO = "portfolio"
    STRATEGY = "strategy"
    EXECUTION = "execution"
    RISK = "risk"
    CLOCK = "clock"


@dataclass
class SnapshotMetadata:
    """快照元数据"""
    snapshot_id: str
    snapshot_type: SnapshotType
    runtime_id: str
    
    timestamp: datetime
    sequence: int
    
    state_hash: str
    size_bytes: int
    
    parent_snapshot_id: Optional[str] = None
    
    tags: List[str] = field(default_factory=list)
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "snapshot_type": self.snapshot_type.value,
            "runtime_id": self.runtime_id,
            "timestamp": self.timestamp.isoformat(),
            "sequence": self.sequence,
            "state_hash": self.state_hash,
            "size_bytes": self.size_bytes,
            "parent_snapshot_id": self.parent_snapshot_id,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class PortfolioSnapshot:
    """组合快照"""
    timestamp: datetime
    
    capital: float
    available_capital: float
    locked_capital: float
    
    positions: Dict[str, Dict[str, Any]]
    
    total_pnl: float
    unrealized_pnl: float
    realized_pnl: float
    
    exposure_by_exchange: Dict[str, float]
    exposure_by_symbol: Dict[str, float]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "capital": self.capital,
            "available_capital": self.available_capital,
            "locked_capital": self.locked_capital,
            "positions": self.positions,
            "total_pnl": self.total_pnl,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "exposure_by_exchange": self.exposure_by_exchange,
            "exposure_by_symbol": self.exposure_by_symbol,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PortfolioSnapshot":
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            capital=data["capital"],
            available_capital=data["available_capital"],
            locked_capital=data["locked_capital"],
            positions=data["positions"],
            total_pnl=data["total_pnl"],
            unrealized_pnl=data["unrealized_pnl"],
            realized_pnl=data["realized_pnl"],
            exposure_by_exchange=data["exposure_by_exchange"],
            exposure_by_symbol=data["exposure_by_symbol"],
        )


@dataclass
class StrategySnapshot:
    """策略快照"""
    timestamp: datetime
    strategy_id: str
    
    state: str
    phase: str
    
    signals: List[Dict[str, Any]]
    pending_orders: List[Dict[str, Any]]
    
    parameters: Dict[str, Any]
    metrics: Dict[str, Any]
    
    regime_state: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "strategy_id": self.strategy_id,
            "state": self.state,
            "phase": self.phase,
            "signals": self.signals,
            "pending_orders": self.pending_orders,
            "parameters": self.parameters,
            "metrics": self.metrics,
            "regime_state": self.regime_state,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StrategySnapshot":
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            strategy_id=data["strategy_id"],
            state=data["state"],
            phase=data["phase"],
            signals=data["signals"],
            pending_orders=data["pending_orders"],
            parameters=data["parameters"],
            metrics=data["metrics"],
            regime_state=data.get("regime_state"),
        )


@dataclass
class ExecutionSnapshot:
    """执行快照"""
    timestamp: datetime
    
    open_orders: Dict[str, Dict[str, Any]]
    recent_fills: List[Dict[str, Any]]
    
    order_count: int
    fill_count: int
    reject_count: int
    
    exchange_states: Dict[str, Dict[str, Any]]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "open_orders": self.open_orders,
            "recent_fills": self.recent_fills,
            "order_count": self.order_count,
            "fill_count": self.fill_count,
            "reject_count": self.reject_count,
            "exchange_states": self.exchange_states,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionSnapshot":
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            open_orders=data["open_orders"],
            recent_fills=data["recent_fills"],
            order_count=data["order_count"],
            fill_count=data["fill_count"],
            reject_count=data["reject_count"],
            exchange_states=data["exchange_states"],
        )


@dataclass
class RiskSnapshot:
    """风控快照"""
    timestamp: datetime
    
    active_rules: List[str]
    rule_states: Dict[str, Dict[str, Any]]
    
    current_exposure: float
    max_exposure: float
    
    drawdown: float
    max_drawdown: float
    
    leverage: float
    max_leverage: float
    
    violations: List[Dict[str, Any]]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "active_rules": self.active_rules,
            "rule_states": self.rule_states,
            "current_exposure": self.current_exposure,
            "max_exposure": self.max_exposure,
            "drawdown": self.drawdown,
            "max_drawdown": self.max_drawdown,
            "leverage": self.leverage,
            "max_leverage": self.max_leverage,
            "violations": self.violations,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RiskSnapshot":
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            active_rules=data["active_rules"],
            rule_states=data["rule_states"],
            current_exposure=data["current_exposure"],
            max_exposure=data["max_exposure"],
            drawdown=data["drawdown"],
            max_drawdown=data["max_drawdown"],
            leverage=data["leverage"],
            max_leverage=data["max_leverage"],
            violations=data["violations"],
        )


@dataclass
class FullSnapshot:
    """完整系统快照"""
    snapshot_id: str
    runtime_id: str
    timestamp: datetime
    sequence: int
    
    portfolio: Optional[PortfolioSnapshot] = None
    strategy: Optional[StrategySnapshot] = None
    execution: Optional[ExecutionSnapshot] = None
    risk: Optional[RiskSnapshot] = None
    
    clock_state: Dict[str, Any] = field(default_factory=dict)
    runtime_state: Dict[str, Any] = field(default_factory=dict)
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def compute_hash(self) -> str:
        """计算状态哈希"""
        state_data = {
            "portfolio": self.portfolio.to_dict() if self.portfolio else None,
            "strategy": self.strategy.to_dict() if self.strategy else None,
            "execution": self.execution.to_dict() if self.execution else None,
            "risk": self.risk.to_dict() if self.risk else None,
            "clock_state": self.clock_state,
        }
        state_str = json.dumps(state_data, sort_keys=True)
        return hashlib.sha256(state_str.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "runtime_id": self.runtime_id,
            "timestamp": self.timestamp.isoformat(),
            "sequence": self.sequence,
            "state_hash": self.compute_hash(),
            "portfolio": self.portfolio.to_dict() if self.portfolio else None,
            "strategy": self.strategy.to_dict() if self.strategy else None,
            "execution": self.execution.to_dict() if self.execution else None,
            "risk": self.risk.to_dict() if self.risk else None,
            "clock_state": self.clock_state,
            "runtime_state": self.runtime_state,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FullSnapshot":
        return cls(
            snapshot_id=data["snapshot_id"],
            runtime_id=data["runtime_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            sequence=data["sequence"],
            portfolio=PortfolioSnapshot.from_dict(data["portfolio"]) if data.get("portfolio") else None,
            strategy=StrategySnapshot.from_dict(data["strategy"]) if data.get("strategy") else None,
            execution=ExecutionSnapshot.from_dict(data["execution"]) if data.get("execution") else None,
            risk=RiskSnapshot.from_dict(data["risk"]) if data.get("risk") else None,
            clock_state=data.get("clock_state", {}),
            runtime_state=data.get("runtime_state", {}),
            metadata=data.get("metadata", {}),
        )


class SnapshotManager:
    """快照管理器
    
    提供完整的快照和恢复能力
    """
    
    def __init__(self):
        self.clickhouse: Optional[ClickHouseManager] = None
        
        self._snapshots: Dict[str, FullSnapshot] = {}
        self._snapshot_sequence = 0
        
        self._portfolio_engine = None
        self._strategy_engine = None
        self._execution_engine = None
        self._risk_engine = None
        self._clock = None
        
        self._auto_snapshot_interval = 60
        self._max_snapshots = 1000
    
    def set_portfolio_engine(self, engine: Any) -> None:
        self._portfolio_engine = engine
    
    def set_strategy_engine(self, engine: Any) -> None:
        self._strategy_engine = engine
    
    def set_execution_engine(self, engine: Any) -> None:
        self._execution_engine = engine
    
    def set_risk_engine(self, engine: Any) -> None:
        self._risk_engine = engine
    
    def set_clock(self, clock: Any) -> None:
        self._clock = clock
    
    async def create_snapshot(
        self,
        runtime_id: str,
        snapshot_type: SnapshotType = SnapshotType.FULL,
        tags: Optional[List[str]] = None,
    ) -> FullSnapshot:
        """创建快照"""
        self._snapshot_sequence += 1
        
        snapshot = FullSnapshot(
            snapshot_id=f"snap_{uuid.uuid4().hex[:12]}",
            runtime_id=runtime_id,
            timestamp=datetime.utcnow(),
            sequence=self._snapshot_sequence,
        )
        
        if snapshot_type in [SnapshotType.FULL, SnapshotType.PORTFOLIO]:
            snapshot.portfolio = await self._capture_portfolio()
        
        if snapshot_type in [SnapshotType.FULL, SnapshotType.STRATEGY]:
            snapshot.strategy = await self._capture_strategy()
        
        if snapshot_type in [SnapshotType.FULL, SnapshotType.EXECUTION]:
            snapshot.execution = await self._capture_execution()
        
        if snapshot_type in [SnapshotType.FULL, SnapshotType.RISK]:
            snapshot.risk = await self._capture_risk()
        
        if self._clock:
            snapshot.clock_state = {
                "current_time": self._clock.now().isoformat(),
                "step_count": self._clock.get_step_count(),
                "mode": self._clock.get_mode().value,
            }
        
        snapshot.metadata = {
            "tags": tags or [],
            "state_hash": snapshot.compute_hash(),
        }
        
        self._snapshots[snapshot.snapshot_id] = snapshot
        
        if len(self._snapshots) > self._max_snapshots:
            oldest_id = min(
                self._snapshots.keys(),
                key=lambda x: self._snapshots[x].sequence
            )
            del self._snapshots[oldest_id]
        
        logger.info(f"Snapshot created: {snapshot.snapshot_id} (hash={snapshot.compute_hash()})")
        return snapshot
    
    async def _capture_portfolio(self) -> Optional[PortfolioSnapshot]:
        """捕获组合状态"""
        if not self._portfolio_engine:
            return None
        
        try:
            if hasattr(self._portfolio_engine, 'get_snapshot'):
                return await self._portfolio_engine.get_snapshot()
            
            if hasattr(self._portfolio_engine, 'get_state'):
                state = self._portfolio_engine.get_state()
                return PortfolioSnapshot(
                    timestamp=datetime.utcnow(),
                    capital=state.get("capital", 0),
                    available_capital=state.get("available_capital", 0),
                    locked_capital=state.get("locked_capital", 0),
                    positions=state.get("positions", {}),
                    total_pnl=state.get("total_pnl", 0),
                    unrealized_pnl=state.get("unrealized_pnl", 0),
                    realized_pnl=state.get("realized_pnl", 0),
                    exposure_by_exchange=state.get("exposure_by_exchange", {}),
                    exposure_by_symbol=state.get("exposure_by_symbol", {}),
                )
        except Exception as e:
            logger.error(f"Failed to capture portfolio: {e}")
        
        return None
    
    async def _capture_strategy(self) -> Optional[StrategySnapshot]:
        """捕获策略状态"""
        if not self._strategy_engine:
            return None
        
        try:
            if hasattr(self._strategy_engine, 'get_snapshot'):
                return await self._strategy_engine.get_snapshot()
            
            if hasattr(self._strategy_engine, 'get_state'):
                state = self._strategy_engine.get_state()
                return StrategySnapshot(
                    timestamp=datetime.utcnow(),
                    strategy_id=state.get("strategy_id", ""),
                    state=state.get("state", ""),
                    phase=state.get("phase", ""),
                    signals=state.get("signals", []),
                    pending_orders=state.get("pending_orders", []),
                    parameters=state.get("parameters", {}),
                    metrics=state.get("metrics", {}),
                    regime_state=state.get("regime_state"),
                )
        except Exception as e:
            logger.error(f"Failed to capture strategy: {e}")
        
        return None
    
    async def _capture_execution(self) -> Optional[ExecutionSnapshot]:
        """捕获执行状态"""
        if not self._execution_engine:
            return None
        
        try:
            if hasattr(self._execution_engine, 'get_snapshot'):
                return await self._execution_engine.get_snapshot()
            
            if hasattr(self._execution_engine, 'get_state'):
                state = self._execution_engine.get_state()
                return ExecutionSnapshot(
                    timestamp=datetime.utcnow(),
                    open_orders=state.get("open_orders", {}),
                    recent_fills=state.get("recent_fills", []),
                    order_count=state.get("order_count", 0),
                    fill_count=state.get("fill_count", 0),
                    reject_count=state.get("reject_count", 0),
                    exchange_states=state.get("exchange_states", {}),
                )
        except Exception as e:
            logger.error(f"Failed to capture execution: {e}")
        
        return None
    
    async def _capture_risk(self) -> Optional[RiskSnapshot]:
        """捕获风控状态"""
        if not self._risk_engine:
            return None
        
        try:
            if hasattr(self._risk_engine, 'get_snapshot'):
                return await self._risk_engine.get_snapshot()
            
            if hasattr(self._risk_engine, 'get_state'):
                state = self._risk_engine.get_state()
                return RiskSnapshot(
                    timestamp=datetime.utcnow(),
                    active_rules=state.get("active_rules", []),
                    rule_states=state.get("rule_states", {}),
                    current_exposure=state.get("current_exposure", 0),
                    max_exposure=state.get("max_exposure", 0),
                    drawdown=state.get("drawdown", 0),
                    max_drawdown=state.get("max_drawdown", 0),
                    leverage=state.get("leverage", 0),
                    max_leverage=state.get("max_leverage", 0),
                    violations=state.get("violations", []),
                )
        except Exception as e:
            logger.error(f"Failed to capture risk: {e}")
        
        return None
    
    async def restore_snapshot(
        self,
        snapshot_id: str,
    ) -> bool:
        """恢复快照"""
        snapshot = self._snapshots.get(snapshot_id)
        if not snapshot:
            logger.error(f"Snapshot not found: {snapshot_id}")
            return False
        
        try:
            if snapshot.portfolio and self._portfolio_engine:
                if hasattr(self._portfolio_engine, 'restore_snapshot'):
                    await self._portfolio_engine.restore_snapshot(snapshot.portfolio)
                elif hasattr(self._portfolio_engine, 'restore_state'):
                    await self._portfolio_engine.restore_state(snapshot.portfolio.to_dict())
            
            if snapshot.strategy and self._strategy_engine:
                if hasattr(self._strategy_engine, 'restore_snapshot'):
                    await self._strategy_engine.restore_snapshot(snapshot.strategy)
                elif hasattr(self._strategy_engine, 'restore_state'):
                    await self._strategy_engine.restore_state(snapshot.strategy.to_dict())
            
            if snapshot.execution and self._execution_engine:
                if hasattr(self._execution_engine, 'restore_snapshot'):
                    await self._execution_engine.restore_snapshot(snapshot.execution)
                elif hasattr(self._execution_engine, 'restore_state'):
                    await self._execution_engine.restore_state(snapshot.execution.to_dict())
            
            if snapshot.risk and self._risk_engine:
                if hasattr(self._risk_engine, 'restore_snapshot'):
                    await self._risk_engine.restore_snapshot(snapshot.risk)
                elif hasattr(self._risk_engine, 'restore_state'):
                    await self._risk_engine.restore_state(snapshot.risk.to_dict())
            
            if snapshot.clock_state and self._clock:
                if "current_time" in snapshot.clock_state:
                    target_time = datetime.fromisoformat(snapshot.clock_state["current_time"])
                    self._clock.advance_to(target_time)
            
            logger.info(f"Snapshot restored: {snapshot_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore snapshot: {e}")
            return False
    
    async def verify_snapshot(
        self,
        snapshot_id: str,
    ) -> Dict[str, Any]:
        """验证快照"""
        snapshot = self._snapshots.get(snapshot_id)
        if not snapshot:
            return {"valid": False, "error": "Snapshot not found"}
        
        current_hash = snapshot.compute_hash()
        stored_hash = snapshot.metadata.get("state_hash", "")
        
        return {
            "valid": current_hash == stored_hash,
            "current_hash": current_hash,
            "stored_hash": stored_hash,
            "snapshot_id": snapshot_id,
            "timestamp": snapshot.timestamp.isoformat(),
        }
    
    def get_snapshot(self, snapshot_id: str) -> Optional[FullSnapshot]:
        """获取快照"""
        return self._snapshots.get(snapshot_id)
    
    def get_all_snapshots(self) -> List[FullSnapshot]:
        """获取所有快照"""
        return list(self._snapshots.values())
    
    def get_latest_snapshot(self) -> Optional[FullSnapshot]:
        """获取最新快照"""
        if not self._snapshots:
            return None
        return max(self._snapshots.values(), key=lambda x: x.sequence)
    
    def delete_snapshot(self, snapshot_id: str) -> bool:
        """删除快照"""
        if snapshot_id in self._snapshots:
            del self._snapshots[snapshot_id]
            logger.info(f"Snapshot deleted: {snapshot_id}")
            return True
        return False


_snapshot_manager: Optional[SnapshotManager] = None


def get_snapshot_manager() -> SnapshotManager:
    """获取快照管理器实例"""
    global _snapshot_manager
    if _snapshot_manager is None:
        _snapshot_manager = SnapshotManager()
    return _snapshot_manager
