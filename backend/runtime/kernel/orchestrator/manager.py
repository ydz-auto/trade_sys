"""
Runtime Orchestrator - Runtime 总控制器

核心职责:
1. 统一管理所有 runtime
2. 协调 runtime 启动顺序 (DependencyGraph 驱动)
3. 模式切换编排
4. 健康检查协调 (HealthSystem 统一)
"""
from typing import Dict, Any, Optional, List, Callable, Set
from datetime import datetime
from dataclasses import dataclass, field
import asyncio
import os

from domain.trading_mode import TradingMode
from runtimes.trading_mode_manager import get_trading_mode_manager
from .registry import RuntimeRegistry, RuntimeType, RuntimeState, RuntimeInfo, get_runtime_registry
from .lifecycle import RuntimeLifecycle, get_runtime_lifecycle
from .catalog import get_mode_runtime_types, iter_runtime_specs
from runtime.kernel.orchestrator.dependency_graph import get_dependency_graph
from runtime.kernel.lifecycle.runtime_health import get_health_system, HealthStatus
from runtime.kernel.lifecycle.state_machine import get_state_machine, RuntimeState as LifecycleState
from runtime.kernel.state import get_runtime_state_store
from infrastructure.logging import get_logger
from infrastructure.utilities.runtime_clock import now_ms

logger = get_logger("runtime.orchestrator")


@dataclass
class OrchestratorConfig:
    auto_start: bool = True
    auto_recover: bool = True
    health_check_interval: float = 10.0
    startup_timeout: float = 30.0
    shutdown_timeout: float = 10.0


@dataclass
class OrchestratorStatus:
    is_running: bool
    mode: TradingMode
    active_runtimes: int
    failed_runtimes: int
    uptime_seconds: float
    started_at: Optional[datetime] = None


class RuntimeOrchestrator:
    _instance: Optional['RuntimeOrchestrator'] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config: Optional[OrchestratorConfig] = None):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._initialized = True
        self._config = config or OrchestratorConfig()
        
        self._mode_manager = get_trading_mode_manager()
        self._registry = get_runtime_registry()
        self._lifecycle = get_runtime_lifecycle()
        self._state_store = get_runtime_state_store()
        
        self._dependency_graph = get_dependency_graph()
        self._health_system = get_health_system()
        self._state_machine = get_state_machine()
        
        self._is_running = False
        self._started_at: Optional[datetime] = None
        self._health_check_task: Optional[asyncio.Task] = None
        self._auto_register = os.environ.get("ORCHESTRATOR_AUTO_REGISTER", "true").lower() == "true"
        
        self._on_mode_change_callbacks: List[Callable] = []
        
        self._mode_manager.register_mode_change_callback(self._on_mode_changed)
        
        self._stats = {
            "total_starts": 0,
            "total_stops": 0,
            "mode_changes": 0,
        }
        
        logger.info("RuntimeOrchestrator initialized with DependencyGraph + HealthSystem")

    async def start(self) -> Dict[str, Any]:
        if self._is_running:
            return {"success": False, "error": "Already running"}
        
        logger.info("Starting Runtime Orchestrator...")
        
        try:
            from infrastructure.messaging.event_journal import get_event_journal
            journal = await get_event_journal()
            from runtime.kernel.event.runtime_bus import get_runtime_bus
            bus = get_runtime_bus()
            bus.set_journal(journal)
            logger.info("EventJournal attached to RuntimeBus")
        except Exception as e:
            logger.warning(f"EventJournal init skipped: {e}")
        
        self._is_running = True
        self._started_at = datetime.fromtimestamp(now_ms() / 1000)
        
        mode = self._mode_manager.mode
        runtime_types = set(get_mode_runtime_types(mode))

        if self._auto_register:
            self._ensure_mode_runtimes_registered(runtime_types, mode)

        runtime_types = {
            runtime_type
            for runtime_type in runtime_types
            if self._registry.get_by_type(runtime_type)
        }
        
        startup_order_types = self._dependency_graph.get_startup_order(runtime_types)
        
        logger.info(f"DependencyGraph startup order: {[rt.value for rt in startup_order_types]}")
        
        results = {"started": [], "failed": [], "skipped": []}
        started_types: Set[RuntimeType] = set()
        
        for runtime_type in startup_order_types:
            can_start, missing = self._dependency_graph.can_start(
                runtime_type,
                started_types,
                target_runtimes=runtime_types,
            )
            
            if not can_start:
                logger.warning(f"Skipping {runtime_type.value}: missing dependencies {[m.value for m in missing]}")
                results["skipped"].append(runtime_type.value)
                continue
            
            runtime_infos = self._registry.get_by_type(runtime_type)
            
            for info in runtime_infos:
                self._state_machine.register(info.runtime_id, LifecycleState.CREATED)
                await self._state_machine.transition(info.runtime_id, LifecycleState.STARTING, reason="orchestrator_start")
                
                try:
                    success = await self._lifecycle.start(info.runtime_id)
                    if success:
                        await self._state_machine.transition(info.runtime_id, LifecycleState.RUNNING, reason="started")
                        results["started"].append(info.runtime_id)
                        started_types.add(runtime_type)
                    else:
                        await self._state_machine.transition(info.runtime_id, LifecycleState.FAILED, reason="start_failed")
                        results["failed"].append(info.runtime_id)
                except Exception as e:
                    logger.error(f"Failed to start {info.runtime_id}: {e}")
                    await self._state_machine.transition(info.runtime_id, LifecycleState.FAILED, reason=str(e))
                    results["failed"].append(info.runtime_id)
        
        await self._health_system.start()
        
        self._stats["total_starts"] += 1
        
        logger.info(f"Runtime Orchestrator started: {len(results['started'])} runtimes")
        
        return {
            "success": True,
            "mode": mode.value,
            "results": results,
            "startup_order": [rt.value for rt in startup_order_types],
        }

    async def stop(self) -> Dict[str, Any]:
        if not self._is_running:
            return {"success": False, "error": "Not running"}
        
        logger.info("Stopping Runtime Orchestrator...")
        
        try:
            from infrastructure.messaging.event_journal import stop_event_journal
            await stop_event_journal()
        except Exception as e:
            logger.warning(f"EventJournal stop skipped: {e}")
        
        await self._health_system.stop()
        
        mode = self._mode_manager.mode
        runtime_types = {
            runtime_type
            for runtime_type in set(get_mode_runtime_types(mode))
            if self._registry.get_by_type(runtime_type)
        }
        
        shutdown_order_types = self._dependency_graph.get_shutdown_order(runtime_types)
        
        results = {"stopped": [], "failed": []}
        
        for runtime_type in shutdown_order_types:
            runtime_infos = self._registry.get_by_type(runtime_type)
            
            for info in runtime_infos:
                try:
                    await self._state_machine.transition(info.runtime_id, LifecycleState.STOPPING, reason="orchestrator_stop")
                    
                    success = await self._lifecycle.stop(info.runtime_id)
                    if success:
                        await self._state_machine.transition(info.runtime_id, LifecycleState.STOPPED, reason="stopped")
                        results["stopped"].append(info.runtime_id)
                    else:
                        results["failed"].append(info.runtime_id)
                except Exception as e:
                    logger.error(f"Failed to stop {info.runtime_id}: {e}")
                    results["failed"].append(info.runtime_id)
        
        self._is_running = False
        self._stats["total_stops"] += 1
        
        logger.info(f"Runtime Orchestrator stopped: {len(results['stopped'])} runtimes")
        
        return {
            "success": True,
            "results": results,
            "shutdown_order": [rt.value for rt in shutdown_order_types],
        }

    async def restart(self) -> Dict[str, Any]:
        await self.stop()
        await asyncio.sleep(1)
        return await self.start()

    async def switch_mode(self, target_mode: TradingMode, reason: str = "") -> Dict[str, Any]:
        logger.info(f"Switching mode from {self._mode_manager.mode.value} to {target_mode.value}")
        
        result = await self._mode_manager.transition_to(target_mode, reason=reason)
        
        if not result.get("success"):
            return result
        
        self._stats["mode_changes"] += 1
        
        for callback in self._on_mode_change_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(target_mode)
                else:
                    callback(target_mode)
            except Exception as e:
                logger.error(f"Mode change callback error: {e}")
        
        return result

    async def _on_mode_changed(self, old_mode: TradingMode, new_mode: TradingMode) -> None:
        logger.info(f"Mode changed: {old_mode.value} -> {new_mode.value}")
        
        if self._is_running:
            await self.stop()
            await asyncio.sleep(0.5)
            await self.start()

    async def _health_check_loop(self) -> None:
        while self._is_running:
            try:
                await self._run_health_checks()
                await asyncio.sleep(self._config.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
                await asyncio.sleep(5)

    async def _run_health_checks(self) -> None:
        active = self._registry.get_active()
        
        for info in active:
            try:
                if hasattr(info.instance, 'health_check'):
                    health = await info.instance.health_check()
                    if not health.get("healthy", True):
                        logger.warning(f"Runtime {info.runtime_id} unhealthy: {health}")
                        
                        if self._config.auto_recover:
                            await self._lifecycle.recover(info.runtime_id)
            except Exception as e:
                logger.error(f"Health check failed for {info.runtime_id}: {e}")

    def _ensure_mode_runtimes_registered(
        self,
        runtime_types: Set[RuntimeType],
        mode: TradingMode,
    ) -> None:
        for spec in iter_runtime_specs(runtime_types):
            if self._registry.get_by_type(spec.runtime_type):
                continue

            try:
                instance = spec.factory()
                self.register_runtime(
                    spec.runtime_type,
                    instance,
                    runtime_id=spec.runtime_id,
                    mode=mode,
                    priority=spec.priority,
                    dependencies=list(spec.dependencies),
                    metadata={"source": "runtime_catalog"},
                )
                self._dependency_graph.register(
                    spec.runtime_type,
                    dependencies=set(spec.dependencies),
                    priority=spec.priority,
                    optional=spec.optional,
                )
            except Exception as e:
                logger.error(f"Failed to register {spec.runtime_id}: {e}")

    def _get_governor_stats(self, status: OrchestratorStatus) -> Dict[str, Any]:
        events_processed = 0
        errors = 0

        for info in self._registry.get_all():
            context = getattr(info.instance, "context", None)
            stats = getattr(context, "stats", {}) or {}
            for key in ("events_processed", "processed_events", "collection_cycles", "orders_executed"):
                value = stats.get(key)
                if isinstance(value, (int, float)):
                    events_processed += int(value)

            error_count = stats.get("errors")
            if isinstance(error_count, (int, float)):
                errors += int(error_count)
            errors += len(getattr(context, "errors", []) or [])

        return {
            "events_processed": events_processed,
            "errors": errors,
            "uptime_seconds": status.uptime_seconds,
        }

    def _get_load_metrics(self) -> Dict[str, float]:
        cpu_percent = 0.0
        memory_percent = 0.0

        try:
            import psutil

            process = psutil.Process()
            cpu_percent = float(process.cpu_percent(interval=None))
            memory_percent = float(process.memory_percent())
        except Exception:
            pass

        uptime = self.get_status().uptime_seconds
        events = self._get_governor_stats(self.get_status())["events_processed"]
        event_rate = float(events / uptime) if uptime > 0 else 0.0

        return {
            "cpu_percent": cpu_percent,
            "memory_percent": memory_percent,
            "event_rate": event_rate,
        }

    def register_runtime(
        self,
        runtime_type: RuntimeType,
        instance: Any,
        **kwargs,
    ) -> str:
        return self._registry.register(runtime_type, instance, **kwargs)

    def on_mode_change(self, callback: Callable) -> None:
        self._on_mode_change_callbacks.append(callback)

    def get_status(self) -> OrchestratorStatus:
        active = self._registry.get_active()
        failed = [
            r for r in self._registry.get_all()
            if r.state == RuntimeState.FAILED
        ]
        
        uptime = 0.0
        if self._started_at:
            uptime = (datetime.fromtimestamp(now_ms() / 1000) - self._started_at).total_seconds()
        
        return OrchestratorStatus(
            is_running=self._is_running,
            mode=self._mode_manager.mode,
            active_runtimes=len(active),
            failed_runtimes=len(failed),
            uptime_seconds=uptime,
            started_at=self._started_at,
        )

    def get_runtime_info(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": info.runtime_id,
                "type": info.runtime_type.value,
                "state": info.state.value,
                "mode": info.mode.value if info.mode else None,
                "priority": info.priority,
            }
            for info in self._registry.get_all()
        ]

    def get_stats(self) -> Dict[str, Any]:
        status = self.get_status()
        health_metrics = self._health_system.get_metrics()
        governor_stats = self._get_governor_stats(status)
        current_mode = "normal" if status.failed_runtimes == 0 else "degraded"
        return {
            "state": "running" if status.is_running else "stopped",
            "is_running": status.is_running,
            "mode": status.mode.value,
            "active_runtimes": status.active_runtimes,
            "failed_runtimes": status.failed_runtimes,
            "uptime_seconds": status.uptime_seconds,
            "governor_stats": governor_stats,
            "degradation_stats": {
                "current_mode": current_mode,
                "load_metrics": self._get_load_metrics(),
            },
            "runtimes": self.get_runtime_info(),
            "stats": self._stats.copy(),
            "registry": self._registry.get_stats(),
            "health": {
                "total_runtimes": health_metrics.total_runtimes,
                "healthy": health_metrics.healthy_count,
                "degraded": health_metrics.degraded_count,
                "unhealthy": health_metrics.unhealthy_count,
                "critical": health_metrics.critical_count,
                "avg_latency_ms": health_metrics.avg_latency_ms,
                "uptime_percentage": health_metrics.uptime_percentage,
            },
            "state_machine": self._state_machine.get_stats(),
            "dependency_graph": self._dependency_graph.get_graph(),
        }
    
    def get_health(self) -> Dict[str, Any]:
        return self._health_system.get_stats()
    
    def get_alerts(self, limit: int = 20) -> List[Dict[str, Any]]:
        alerts = self._health_system.get_alerts(limit=limit)
        return [
            {
                "alert_id": a.alert_id,
                "level": a.level.value,
                "runtime_id": a.runtime_id,
                "message": a.message,
                "timestamp": a.timestamp.isoformat(),
                "acknowledged": a.acknowledged,
            }
            for a in alerts
        ]


def get_runtime_orchestrator() -> RuntimeOrchestrator:
    return RuntimeOrchestrator()
