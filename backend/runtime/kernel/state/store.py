"""
Runtime State Store - 运行态状态只读聚合视图

核心职责:
1. 聚合各 Runtime 的状态，作为 Frontend 的唯一读取来源
2. 不可变快照
3. 订阅通知

状态归属 (Single Source of Truth):
    market_state    → RuntimeContext (market context)
    signal_state    → SignalRuntime
    execution_state → ExecutionRuntime
    portfolio_state → PortfolioRuntime
    risk_state      → RuntimeContext (risk context)
    runtime_state   → RuntimeOrchestrator
    feature_state   → FeatureRuntime / FeatureMatrixRuntime
    correlation     → CorrelationRuntime
    projection      → ProjectionRuntime
    replay          → ReplayRuntime

本 Store 不持有业务状态，只聚合读取。
写入通过 register_state_provider() 注册状态提供者。
"""

from typing import Dict, Any, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, field
import json

from domain.trading_mode import TradingMode
from runtimes.trading_mode_manager import get_trading_mode_manager
from infrastructure.logging import get_logger
from infrastructure.utilities.runtime_clock import get_clock, now_ms
from infrastructure.storage.immutable_snapshot import get_immutable_snapshot_store

logger = get_logger("runtime.state_store")


StateProvider = Callable[[], Dict[str, Any]]


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

        self._clock = get_clock()
        self._immutable_snapshot_store = get_immutable_snapshot_store("state")

        self._providers: Dict[str, StateProvider] = {}

        self._runtime_meta: Dict[str, Dict[str, Any]] = {
            "runtime": {},
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
            "reads": 0,
        }

        self._register_default_providers()

        logger.info("RuntimeStateStore initialized (read-only aggregation, no business state)")

    def _register_default_providers(self) -> None:
        self._providers["execution"] = self._make_provider("runtime.execution_runtime.runtime", "get_execution_runtime")
        self._providers["portfolio"] = self._make_provider("runtime.portfolio_runtime", "get_portfolio_runtime")
        self._providers["signal"] = self._make_provider("runtime.signal_runtime.runtime", "get_signal_runtime")
        self._providers["feature"] = self._make_provider("runtime.feature_matrix_runtime", "get_feature_matrix_runtime")
        self._providers["correlation"] = self._make_provider("runtime.correlation_runtime.runtime", "get_correlation_runtime")
        self._providers["projection"] = self._make_provider("runtime.projection_runtime.runtime", "get_projection_runtime")
        self._providers["replay"] = self._make_provider("runtime.replay_runtime.runtime", "get_replay_runtime")
        self._providers["market"] = self._make_provider("runtime.context.runtime_context", "get_runtime_context")
        self._providers["risk"] = self._make_provider("runtime.context.runtime_context", "get_runtime_context")

    def _make_provider(self, module_path: str, getter_name: str) -> StateProvider:
        def _provider() -> Dict[str, Any]:
            try:
                import importlib
                module = importlib.import_module(module_path)
                getter = getattr(module, getter_name)
                runtime = getter()
                if hasattr(runtime, 'get_state'):
                    return runtime.get_state()
                elif hasattr(runtime, 'to_dict'):
                    return runtime.to_dict()
            except Exception as e:
                logger.debug(f"State provider [{module_path}.{getter_name}] failed: {e}")
            return {}
        return _provider

    def register_provider(self, state_type: str, provider: StateProvider) -> None:
        self._providers[state_type] = provider
        logger.info(f"Registered state provider: {state_type}")

    def get_state(self, state_type: str, use_namespace: bool = True) -> Dict[str, Any]:
        self._stats["reads"] += 1

        if state_type == "runtime":
            return self._runtime_meta.get("runtime", {}).copy()

        provider = self._providers.get(state_type)
        if provider:
            return provider()

        return {}

    def get_all_state(self, use_namespace: bool = True) -> Dict[str, Any]:
        self._stats["reads"] += 1

        result = {}
        for state_type in self._providers:
            result[state_type] = self._providers[state_type]()

        result["runtime"] = self._runtime_meta.get("runtime", {}).copy()

        return result

    def set_runtime_state(self, data: Dict[str, Any]) -> None:
        self._runtime_meta["runtime"].update(data)

        current_time = datetime.fromtimestamp(now_ms() / 1000)
        self._version += 1
        self._last_update = current_time
        self._stats["updates"] += 1

        if self._immutable_snapshot_store:
            snapshot_data = {
                "state_type": "runtime",
                "data": data.copy(),
                "clock_mode": self._clock.mode.value,
                "version": self._version,
            }
            self._immutable_snapshot_store.save(snapshot_data, timestamp=current_time)

        for key, value in data.items():
            self._notify_subscribers("runtime", key, value)

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
            timestamp=datetime.fromtimestamp(now_ms() / 1000),
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
        raise NotImplementedError(
            "restore_snapshot() is not supported. "
            "State restore should be done via individual Runtime.restore(), not via StateStore. "
            "StateStore is a read-only aggregation view."
        )

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
            "registered_providers": list(self._providers.keys()),
            "subscribers": {k: len(v) for k, v in self._subscribers.items()},
            "snapshots": len(self._snapshots),
            "stats": self._stats.copy(),
        }


def get_runtime_state_store() -> RuntimeStateStore:
    return RuntimeStateStore()


def get_state(state_type: str, key: str = None) -> Any:
    store = get_runtime_state_store()
    return store.get_state(state_type)
