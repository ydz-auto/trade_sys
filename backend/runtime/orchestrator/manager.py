"""
Runtime Orchestrator - Runtime 总控制器

核心职责:
1. 统一管理所有 runtime
2. 协调 runtime 启动顺序
3. 模式切换编排
4. 健康检查协调
"""
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
from dataclasses import dataclass, field
import asyncio

from domain.trading_mode import TradingMode, get_trading_mode_manager
from .registry import RuntimeRegistry, RuntimeType, RuntimeState, RuntimeInfo, get_runtime_registry
from .lifecycle import RuntimeLifecycle, get_runtime_lifecycle
from runtime.state import get_runtime_state_store
from infrastructure.logging import get_logger

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
        
        self._is_running = False
        self._started_at: Optional[datetime] = None
        self._health_check_task: Optional[asyncio.Task] = None
        
        self._mode_runtimes: Dict[TradingMode, List[RuntimeType]] = {
            TradingMode.BACKTEST: [
                RuntimeType.REPLAY,
                RuntimeType.FEATURE,
                RuntimeType.SIGNAL,
                RuntimeType.PROJECTION,
            ],
            TradingMode.PAPER: [
                RuntimeType.INGESTION,
                RuntimeType.FEATURE,
                RuntimeType.BEHAVIOUR,
                RuntimeType.SIGNAL,
                RuntimeType.EXECUTION,
                RuntimeType.PORTFOLIO,
                RuntimeType.RISK,
                RuntimeType.PROJECTION,
            ],
            TradingMode.LIVE: [
                RuntimeType.INGESTION,
                RuntimeType.MARKET,
                RuntimeType.FEATURE,
                RuntimeType.BEHAVIOUR,
                RuntimeType.SIGNAL,
                RuntimeType.EXECUTION,
                RuntimeType.PORTFOLIO,
                RuntimeType.RISK,
                RuntimeType.PROJECTION,
                RuntimeType.MONITORING,
            ],
        }
        
        self._on_mode_change_callbacks: List[Callable] = []
        
        self._mode_manager.register_mode_change_callback(self._on_mode_changed)
        
        self._stats = {
            "total_starts": 0,
            "total_stops": 0,
            "mode_changes": 0,
        }
        
        logger.info("RuntimeOrchestrator initialized")

    async def start(self) -> Dict[str, Any]:
        if self._is_running:
            return {"success": False, "error": "Already running"}
        
        logger.info("Starting Runtime Orchestrator...")
        
        self._is_running = True
        self._started_at = datetime.now()
        
        mode = self._mode_manager.mode
        runtime_types = self._mode_runtimes.get(mode, [])
        
        startup_order = self._registry.get_startup_order()
        startup_order = [r for r in startup_order if r.runtime_type in runtime_types]
        
        results = {"started": [], "failed": []}
        
        for info in startup_order:
            try:
                success = await self._lifecycle.start(info.runtime_id)
                if success:
                    results["started"].append(info.runtime_id)
                else:
                    results["failed"].append(info.runtime_id)
            except Exception as e:
                logger.error(f"Failed to start {info.runtime_id}: {e}")
                results["failed"].append(info.runtime_id)
        
        if self._config.health_check_interval > 0:
            self._health_check_task = asyncio.create_task(self._health_check_loop())
        
        self._stats["total_starts"] += 1
        
        self._state_store.set_runtime_state({
            "orchestrator_running": True,
            "started_at": self._started_at.isoformat(),
            "mode": mode.value,
        })
        
        logger.info(f"Runtime Orchestrator started: {len(results['started'])} runtimes")
        
        return {
            "success": True,
            "mode": mode.value,
            "results": results,
        }

    async def stop(self) -> Dict[str, Any]:
        if not self._is_running:
            return {"success": False, "error": "Not running"}
        
        logger.info("Stopping Runtime Orchestrator...")
        
        if self._health_check_task:
            self._health_check_task.cancel()
            self._health_check_task = None
        
        active = self._registry.get_active()
        results = {"stopped": [], "failed": []}
        
        for info in reversed(active):
            try:
                success = await self._lifecycle.stop(info.runtime_id)
                if success:
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
            uptime = (datetime.now() - self._started_at).total_seconds()
        
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
        return {
            "is_running": status.is_running,
            "mode": status.mode.value,
            "active_runtimes": status.active_runtimes,
            "failed_runtimes": status.failed_runtimes,
            "uptime_seconds": status.uptime_seconds,
            "stats": self._stats.copy(),
            "registry": self._registry.get_stats(),
        }


def get_runtime_orchestrator() -> RuntimeOrchestrator:
    return RuntimeOrchestrator()
