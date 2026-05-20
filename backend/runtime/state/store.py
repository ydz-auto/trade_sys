"""
Runtime State Store - 运行态状态存储

核心职责:
1. 统一所有系统状态
2. 作为 Frontend 的唯一状态来源
3. 支持按 namespace 隔离

状态结构:
    RuntimeStateStore
    ├─ market_state
    ├─ signal_state
    ├─ execution_state
    ├─ portfolio_state
    ├─ risk_state
    └─ runtime_mode
"""
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, field
import asyncio
import json

from domain.trading_mode import TradingMode, get_trading_mode_manager
from infrastructure.logging import get_logger

logger = get_logger("runtime.state_store")


@dataclass
class StateSnapshot:
    timestamp: datetime
    state_type: str
    data: Dict[str, Any]
    version: int = 1


class RuntimeStateStore:
    _instance: Optional['RuntimeStateStore'] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._initialized = True
        self._mode_manager = get_trading_mode_manager()
        
        self._state: Dict[str, Dict[str, Any]] = {
            "market": {},
            "signal": {},
            "execution": {},
            "portfolio": {},
            "risk": {},
            "runtime": {},
            "feature": {},
            "behaviour": {},
        }
        
        self._isolated_state: Dict[TradingMode, Dict[str, Dict[str, Any]]] = {
            TradingMode.BACKTEST: {k: {} for k in self._state.keys()},
            TradingMode.PAPER: {k: {} for k in self._state.keys()},
            TradingMode.LIVE: {k: {} for k in self._state.keys()},
        }
        
        self._subscribers: Dict[str, list[Callable]] = {}
        
        self._snapshots: list[StateSnapshot] = []
        self._max_snapshots = 1000
        
        self._version = 0
        self._last_update: Optional[datetime] = None
        
        self._stats = {
            "updates": 0,
            "snapshots": 0,
            "subscriber_calls": 0,
        }
        
        logger.info("RuntimeStateStore initialized")

    def _get_state_dict(self, use_namespace: bool = True) -> Dict[str, Dict[str, Any]]:
        if use_namespace:
            mode = self._mode_manager.mode
            return self._isolated_state[mode]
        return self._state

    def set(self, state_type: str, key: str, value: Any, use_namespace: bool = True) -> None:
        state_dict = self._get_state_dict(use_namespace)
        
        if state_type not in state_dict:
            state_dict[state_type] = {}
        
        state_dict[state_type][key] = value
        
        self._version += 1
        self._last_update = datetime.now()
        self._stats["updates"] += 1
        
        self._notify_subscribers(state_type, key, value)

    def get(self, state_type: str, key: str, use_namespace: bool = True) -> Any:
        state_dict = self._get_state_dict(use_namespace)
        return state_dict.get(state_type, {}).get(key)

    def get_state(self, state_type: str, use_namespace: bool = True) -> Dict[str, Any]:
        state_dict = self._get_state_dict(use_namespace)
        return state_dict.get(state_type, {}).copy()

    def get_all_state(self, use_namespace: bool = True) -> Dict[str, Any]:
        state_dict = self._get_state_dict(use_namespace)
        return {k: v.copy() for k, v in state_dict.items()}

    def update(self, state_type: str, data: Dict[str, Any], use_namespace: bool = True) -> None:
        state_dict = self._get_state_dict(use_namespace)
        
        if state_type not in state_dict:
            state_dict[state_type] = {}
        
        state_dict[state_type].update(data)
        
        self._version += 1
        self._last_update = datetime.now()
        self._stats["updates"] += 1
        
        for key, value in data.items():
            self._notify_subscribers(state_type, key, value)

    def clear(self, state_type: str, use_namespace: bool = True) -> None:
        state_dict = self._get_state_dict(use_namespace)
        state_dict[state_type] = {}

    def set_market_state(self, data: Dict[str, Any]) -> None:
        self.update("market", data)

    def set_signal_state(self, data: Dict[str, Any]) -> None:
        self.update("signal", data)

    def set_execution_state(self, data: Dict[str, Any]) -> None:
        self.update("execution", data)

    def set_portfolio_state(self, data: Dict[str, Any]) -> None:
        self.update("portfolio", data)

    def set_risk_state(self, data: Dict[str, Any]) -> None:
        self.update("risk", data)

    def set_runtime_state(self, data: Dict[str, Any]) -> None:
        self.update("runtime", data)

    def get_market_state(self) -> Dict[str, Any]:
        return self.get_state("market")

    def get_signal_state(self) -> Dict[str, Any]:
        return self.get_state("signal")

    def get_execution_state(self) -> Dict[str, Any]:
        return self.get_state("execution")

    def get_portfolio_state(self) -> Dict[str, Any]:
        return self.get_state("portfolio")

    def get_risk_state(self) -> Dict[str, Any]:
        return self.get_state("risk")

    def get_runtime_state(self) -> Dict[str, Any]:
        return self.get_state("runtime")

    def subscribe(self, state_type: str, callback: Callable) -> None:
        if state_type not in self._subscribers:
            self._subscribers[state_type] = []
        self._subscribers[state_type].append(callback)
        logger.info(f"Subscribed to state: {state_type}")

    def unsubscribe(self, state_type: str, callback: Callable) -> None:
        if state_type in self._subscribers:
            self._subscribers[state_type] = [
                cb for cb in self._subscribers[state_type] if cb != callback
            ]

    def _notify_subscribers(self, state_type: str, key: str, value: Any) -> None:
        callbacks = self._subscribers.get(state_type, [])
        for callback in callbacks:
            try:
                callback(state_type, key, value)
                self._stats["subscriber_calls"] += 1
            except Exception as e:
                logger.error(f"Subscriber callback error: {e}")

    def take_snapshot(self, state_type: Optional[str] = None) -> StateSnapshot:
        if state_type:
            data = self.get_state(state_type)
        else:
            data = self.get_all_state()
        
        snapshot = StateSnapshot(
            timestamp=datetime.now(),
            state_type=state_type or "all",
            data=data,
            version=self._version,
        )
        
        self._snapshots.append(snapshot)
        self._stats["snapshots"] += 1
        
        if len(self._snapshots) > self._max_snapshots:
            self._snapshots = self._snapshots[-self._max_snapshots:]
        
        return snapshot

    def get_snapshots(self, state_type: Optional[str] = None, limit: int = 100) -> list[StateSnapshot]:
        snapshots = self._snapshots[-limit:]
        if state_type:
            snapshots = [s for s in snapshots if s.state_type == state_type]
        return snapshots

    def restore_snapshot(self, snapshot: StateSnapshot) -> None:
        if snapshot.state_type == "all":
            for state_type, data in snapshot.data.items():
                self.update(state_type, data)
        else:
            self.update(snapshot.state_type, snapshot.data)
        
        logger.info(f"Restored snapshot: {snapshot.state_type} @ {snapshot.timestamp}")

    def to_json(self) -> str:
        return json.dumps({
            "version": self._version,
            "last_update": self._last_update.isoformat() if self._last_update else None,
            "mode": self._mode_manager.mode.value,
            "state": self.get_all_state(),
        })

    def get_stats(self) -> Dict[str, Any]:
        return {
            "version": self._version,
            "last_update": self._last_update.isoformat() if self._last_update else None,
            "mode": self._mode_manager.mode.value,
            "state_types": list(self._state.keys()),
            "subscribers": {k: len(v) for k, v in self._subscribers.items()},
            "snapshots": len(self._snapshots),
            "stats": self._stats.copy(),
        }


def get_runtime_state_store() -> RuntimeStateStore:
    return RuntimeStateStore()


def set_state(state_type: str, key: str, value: Any) -> None:
    store = get_runtime_state_store()
    store.set(state_type, key, value)


def get_state(state_type: str, key: str = None) -> Any:
    store = get_runtime_state_store()
    if key:
        return store.get(state_type, key)
    return store.get_state(state_type)
