"""
Runtime Registry - Runtime 注册中心

核心职责:
1. 注册所有 runtime
2. 跟踪 runtime 状态
3. 按 mode 分组管理
4. 提供 runtime 发现能力
"""
from typing import Dict, Any, Optional, List, Callable, Type
from enum import Enum
from datetime import datetime
from dataclasses import dataclass, field
import asyncio

from domain.trading_mode import TradingMode
from infrastructure.logging import get_logger

logger = get_logger("runtime.registry")


class RuntimeType(str, Enum):
    MARKET = "market"
    INGESTION = "ingestion"
    FEATURE = "feature"
    BEHAVIOUR = "behaviour"
    SIGNAL = "signal"
    EXECUTION = "execution"
    PORTFOLIO = "portfolio"
    RISK = "risk"
    PROJECTION = "projection"
    REPLAY = "replay"
    NARRATIVE = "narrative"
    MONITORING = "monitoring"


class RuntimeState(str, Enum):
    REGISTERED = "registered"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    DEGRADED = "degraded"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
    RECOVERING = "recovering"


@dataclass
class RuntimeInfo:
    runtime_type: RuntimeType
    runtime_id: str
    instance: Any
    state: RuntimeState = RuntimeState.REGISTERED
    mode: Optional[TradingMode] = None
    priority: int = 0
    dependencies: List[RuntimeType] = field(default_factory=list)
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class RuntimeRegistry:
    _instance: Optional['RuntimeRegistry'] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._initialized = True
        
        self._runtimes: Dict[str, RuntimeInfo] = {}
        self._by_type: Dict[RuntimeType, List[str]] = {rt: [] for rt in RuntimeType}
        self._by_mode: Dict[TradingMode, List[str]] = {tm: [] for tm in TradingMode}
        
        self._state_callbacks: List[Callable[[RuntimeInfo], None]] = []
        
        self._stats = {
            "total_registered": 0,
            "total_started": 0,
            "total_stopped": 0,
            "total_failed": 0,
        }
        
        logger.info("RuntimeRegistry initialized")

    def register(
        self,
        runtime_type: RuntimeType,
        instance: Any,
        runtime_id: Optional[str] = None,
        mode: Optional[TradingMode] = None,
        priority: int = 0,
        dependencies: Optional[List[RuntimeType]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        runtime_id = runtime_id or f"{runtime_type.value}_{len(self._by_type[runtime_type])}"
        
        info = RuntimeInfo(
            runtime_type=runtime_type,
            runtime_id=runtime_id,
            instance=instance,
            mode=mode,
            priority=priority,
            dependencies=dependencies or [],
            metadata=metadata or {},
        )
        
        self._runtimes[runtime_id] = info
        self._by_type[runtime_type].append(runtime_id)
        
        if mode:
            self._by_mode[mode].append(runtime_id)
        
        self._stats["total_registered"] += 1
        
        logger.info(f"Registered runtime: {runtime_id} (type={runtime_type.value}, mode={mode.value if mode else 'all'})")
        
        self._notify_state_change(info)
        
        return runtime_id

    def unregister(self, runtime_id: str) -> bool:
        if runtime_id not in self._runtimes:
            return False
        
        info = self._runtimes[runtime_id]
        
        self._by_type[info.runtime_type].remove(runtime_id)
        if info.mode:
            self._by_mode[info.mode].remove(runtime_id)
        
        del self._runtimes[runtime_id]
        
        logger.info(f"Unregistered runtime: {runtime_id}")
        
        return True

    def get(self, runtime_id: str) -> Optional[RuntimeInfo]:
        return self._runtimes.get(runtime_id)

    def get_by_type(self, runtime_type: RuntimeType) -> List[RuntimeInfo]:
        return [self._runtimes[rid] for rid in self._by_type[runtime_type] if rid in self._runtimes]

    def get_by_mode(self, mode: TradingMode) -> List[RuntimeInfo]:
        return [self._runtimes[rid] for rid in self._by_mode[mode] if rid in self._runtimes]

    def get_all(self) -> List[RuntimeInfo]:
        return list(self._runtimes.values())

    def get_active(self) -> List[RuntimeInfo]:
        return [
            info for info in self._runtimes.values()
            if info.state in (RuntimeState.RUNNING, RuntimeState.DEGRADED)
        ]

    def update_state(self, runtime_id: str, state: RuntimeState, error: Optional[str] = None) -> bool:
        if runtime_id not in self._runtimes:
            return False
        
        info = self._runtimes[runtime_id]
        old_state = info.state
        info.state = state
        info.error = error
        
        if state == RuntimeState.RUNNING and old_state != RuntimeState.RUNNING:
            info.started_at = datetime.now()
            self._stats["total_started"] += 1
        elif state == RuntimeState.STOPPED and old_state != RuntimeState.STOPPED:
            info.stopped_at = datetime.now()
            self._stats["total_stopped"] += 1
        elif state == RuntimeState.FAILED:
            self._stats["total_failed"] += 1
        
        logger.info(f"Runtime {runtime_id} state changed: {old_state.value} -> {state.value}")
        
        self._notify_state_change(info)
        
        return True

    def _notify_state_change(self, info: RuntimeInfo) -> None:
        for callback in self._state_callbacks:
            try:
                callback(info)
            except Exception as e:
                logger.error(f"State callback error: {e}")

    def on_state_change(self, callback: Callable[[RuntimeInfo], None]) -> None:
        self._state_callbacks.append(callback)

    def get_dependencies(self, runtime_id: str) -> List[RuntimeInfo]:
        info = self.get(runtime_id)
        if not info:
            return []
        
        deps = []
        for dep_type in info.dependencies:
            deps.extend(self.get_by_type(dep_type))
        
        return deps

    def get_dependents(self, runtime_id: str) -> List[RuntimeInfo]:
        info = self.get(runtime_id)
        if not info:
            return []
        
        dependents = []
        for other in self._runtimes.values():
            if info.runtime_type in other.dependencies:
                dependents.append(other)
        
        return dependents

    def get_startup_order(self) -> List[RuntimeInfo]:
        runtimes = sorted(
            self._runtimes.values(),
            key=lambda r: r.priority,
            reverse=True
        )
        
        ordered = []
        visited = set()
        
        def visit(info: RuntimeInfo):
            if info.runtime_id in visited:
                return
            visited.add(info.runtime_id)
            
            for dep in self.get_dependencies(info.runtime_id):
                visit(dep)
            
            ordered.append(info)
        
        for info in runtimes:
            visit(info)
        
        return ordered

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_runtimes": len(self._runtimes),
            "by_type": {rt.value: len(ids) for rt, ids in self._by_type.items()},
            "by_mode": {tm.value: len(ids) for tm, ids in self._by_mode.items()},
            "by_state": self._count_by_state(),
            "stats": self._stats.copy(),
        }

    def _count_by_state(self) -> Dict[str, int]:
        counts = {s.value: 0 for s in RuntimeState}
        for info in self._runtimes.values():
            counts[info.state.value] += 1
        return counts


def get_runtime_registry() -> RuntimeRegistry:
    return RuntimeRegistry()
