"""
Runtime Inspector - Runtime 调试器

核心职责:
1. Runtime 状态检查
2. 性能指标收集
3. 调试信息输出
4. 问题诊断
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, field
import asyncio

from .registry import RuntimeState, get_runtime_registry
from .lifecycle import get_runtime_lifecycle
from .timeline import get_runtime_timeline
from runtime.kernel.state import get_runtime_state_store
from runtimes.trading_mode_manager import get_trading_mode_manager
from infrastructure.logging import get_logger
from infrastructure.utilities.runtime_clock import now_ms

logger = get_logger("runtime.inspector")


@dataclass
class InspectionResult:
    runtime_id: str
    timestamp: datetime
    healthy: bool
    state: RuntimeState
    issues: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemInspection:
    timestamp: datetime
    mode: str
    total_runtimes: int
    healthy_runtimes: int
    unhealthy_runtimes: int
    issues: List[str] = field(default_factory=list)
    results: List[InspectionResult] = field(default_factory=list)


class RuntimeInspector:
    _instance: Optional['RuntimeInspector'] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._initialized = True
        
        self._registry = get_runtime_registry()
        self._lifecycle = get_runtime_lifecycle()
        self._timeline = get_runtime_timeline()
        self._state_store = get_runtime_state_store()
        self._mode_manager = get_trading_mode_manager()
        
        self._last_inspection: Optional[SystemInspection] = None
        
        self._stats = {
            "total_inspections": 0,
            "issues_found": 0,
        }
        
        logger.info("RuntimeInspector initialized")

    async def inspect_runtime(self, runtime_id: str) -> InspectionResult:
        info = self._registry.get(runtime_id)
        if not info:
            return InspectionResult(
                runtime_id=runtime_id,
                timestamp=datetime.fromtimestamp(now_ms() / 1000),
                healthy=False,
                state=RuntimeState.STOPPED,
                issues=["Runtime not found"],
            )
        
        issues = []
        metrics = {}
        details = {}
        
        try:
            if hasattr(info.instance, 'health_check'):
                health = await info.instance.health_check()
                metrics["health_check"] = health
                if not health.get("healthy", True):
                    issues.append(f"Health check failed: {health.get('reason', 'unknown')}")
        except Exception as e:
            issues.append(f"Health check error: {e}")
        
        try:
            if hasattr(info.instance, 'get_stats'):
                stats = info.instance.get_stats()
                metrics["runtime_stats"] = stats
        except Exception as e:
            issues.append(f"Stats error: {e}")
        
        try:
            if hasattr(info.instance, 'get_metrics'):
                runtime_metrics = info.instance.get_metrics()
                metrics["performance"] = runtime_metrics
        except Exception as e:
            issues.append(f"Metrics error: {e}")
        
        details["state"] = info.state.value
        details["mode"] = info.mode.value if info.mode else None
        details["priority"] = info.priority
        details["dependencies"] = [d.value for d in info.dependencies]
        details["started_at"] = info.started_at.isoformat() if info.started_at else None
        details["error"] = info.error
        
        if info.state == RuntimeState.FAILED:
            issues.append(f"Runtime in failed state: {info.error}")
        elif info.state == RuntimeState.DEGRADED:
            issues.append("Runtime in degraded state")
        elif info.state == RuntimeState.STOPPED:
            issues.append("Runtime is stopped")
        
        return InspectionResult(
            runtime_id=runtime_id,
            timestamp=datetime.fromtimestamp(now_ms() / 1000),
            healthy=len(issues) == 0,
            state=info.state,
            issues=issues,
            metrics=metrics,
            details=details,
        )

    async def inspect_all(self) -> SystemInspection:
        runtimes = self._registry.get_all()
        
        results = []
        for info in runtimes:
            result = await self.inspect_runtime(info.runtime_id)
            results.append(result)
        
        healthy = [r for r in results if r.healthy]
        unhealthy = [r for r in results if not r.healthy]
        
        all_issues = []
        for r in unhealthy:
            all_issues.extend([f"[{r.runtime_id}] {issue}" for issue in r.issues])
        
        inspection = SystemInspection(
            timestamp=datetime.fromtimestamp(now_ms() / 1000),
            mode=self._mode_manager.mode.value,
            total_runtimes=len(runtimes),
            healthy_runtimes=len(healthy),
            unhealthy_runtimes=len(unhealthy),
            issues=all_issues,
            results=results,
        )
        
        self._last_inspection = inspection
        self._stats["total_inspections"] += 1
        self._stats["issues_found"] += len(all_issues)
        
        return inspection

    def get_runtime_tree(self) -> Dict[str, Any]:
        runtimes = self._registry.get_all()
        
        tree = {}
        for info in runtimes:
            node = {
                "id": info.runtime_id,
                "type": info.runtime_type.value,
                "state": info.state.value,
                "mode": info.mode.value if info.mode else None,
                "dependencies": [d.value for d in info.dependencies],
                "dependents": [],
            }
            
            for dep_type in info.dependencies:
                if dep_type.value not in tree:
                    tree[dep_type.value] = {"children": []}
                tree[dep_type.value]["children"].append(info.runtime_id)
            
            tree[info.runtime_id] = node
        
        return tree

    def get_state_flow(self) -> Dict[str, Any]:
        runtimes = self._registry.get_all()
        
        by_state = {}
        for info in runtimes:
            state = info.state.value
            if state not in by_state:
                by_state[state] = []
            by_state[state].append({
                "id": info.runtime_id,
                "type": info.runtime_type.value,
            })
        
        return by_state

    def get_recent_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        events = self._timeline.get_recent(limit=limit)
        return [e.to_dict() for e in events]

    def get_performance_summary(self) -> Dict[str, Any]:
        runtimes = self._registry.get_active()
        
        summary = {}
        for info in runtimes:
            if hasattr(info.instance, 'get_stats'):
                try:
                    stats = info.instance.get_stats()
                    summary[info.runtime_id] = stats
                except Exception as e:
                    summary[info.runtime_id] = {"error": str(e)}
        
        return summary

    def diagnose(self, runtime_id: str) -> Dict[str, Any]:
        info = self._registry.get(runtime_id)
        if not info:
            return {"error": "Runtime not found"}
        
        diagnosis = {
            "runtime_id": runtime_id,
            "timestamp": datetime.fromtimestamp(now_ms() / 1000).isoformat(),
            "state": info.state.value,
            "issues": [],
            "recommendations": [],
        }
        
        if info.state == RuntimeState.FAILED:
            diagnosis["issues"].append(f"Runtime failed: {info.error}")
            diagnosis["recommendations"].append("Check error logs")
            diagnosis["recommendations"].append("Attempt recovery")
        
        elif info.state == RuntimeState.DEGRADED:
            diagnosis["issues"].append("Runtime is degraded")
            diagnosis["recommendations"].append("Check resource usage")
            diagnosis["recommendations"].append("Consider restart")
        
        elif info.state == RuntimeState.STOPPED:
            diagnosis["issues"].append("Runtime is stopped")
            diagnosis["recommendations"].append("Start runtime if needed")
        
        deps = self._registry.get_dependencies(runtime_id)
        for dep in deps:
            if dep.state in [RuntimeState.FAILED, RuntimeState.STOPPED]:
                diagnosis["issues"].append(f"Dependency {dep.runtime_id} is {dep.state.value}")
                diagnosis["recommendations"].append(f"Fix dependency {dep.runtime_id} first")
        
        dependents = self._registry.get_dependents(runtime_id)
        if dependents and info.state != RuntimeState.RUNNING:
            diagnosis["issues"].append(f"Affects {len(dependents)} dependent runtimes")
        
        return diagnosis

    def get_full_report(self) -> Dict[str, Any]:
        state_store_stats = self._state_store.get_stats()
        timeline_stats = self._timeline.get_stats()
        registry_stats = self._registry.get_stats()
        
        return {
            "timestamp": datetime.fromtimestamp(now_ms() / 1000).isoformat(),
            "mode": self._mode_manager.mode.value,
            "registry": registry_stats,
            "state_store": state_store_stats,
            "timeline": timeline_stats,
            "inspector": self._stats.copy(),
            "last_inspection": {
                "timestamp": self._last_inspection.timestamp.isoformat() if self._last_inspection else None,
                "healthy": self._last_inspection.healthy_runtimes if self._last_inspection else 0,
                "unhealthy": self._last_inspection.unhealthy_runtimes if self._last_inspection else 0,
            } if self._last_inspection else None,
        }

    def get_stats(self) -> Dict[str, Any]:
        return self._stats.copy()


def get_runtime_inspector() -> RuntimeInspector:
    return RuntimeInspector()


async def inspect_system() -> SystemInspection:
    inspector = get_runtime_inspector()
    return await inspector.inspect_all()
