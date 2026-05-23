"""
Runtime Health System - Runtime 健康治理系统

核心职责:
1. 统一所有 runtime 健康状态
2. 心跳检测
3. 延迟监控
4. 自动告警
"""
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import asyncio

from runtime.orchestrator.registry import RuntimeState, get_runtime_registry
from infrastructure.logging import get_logger
from infrastructure.runtime_clock import now_ms

logger = get_logger("runtime.health")


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class AlertLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class HealthCheck:
    runtime_id: str
    status: HealthStatus
    latency_ms: float
    last_heartbeat: datetime
    consecutive_failures: int = 0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthAlert:
    alert_id: str
    level: AlertLevel
    runtime_id: str
    message: str
    timestamp: datetime
    acknowledged: bool = False


@dataclass
class HealthMetrics:
    total_runtimes: int = 0
    healthy_count: int = 0
    degraded_count: int = 0
    unhealthy_count: int = 0
    critical_count: int = 0
    avg_latency_ms: float = 0.0
    uptime_percentage: float = 100.0


class RuntimeHealthSystem:
    _instance: Optional['RuntimeHealthSystem'] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        heartbeat_interval: float = 5.0,
        heartbeat_timeout: float = 30.0,
        degradation_threshold: float = 500.0,
        critical_threshold: float = 2000.0,
    ):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._initialized = True
        self._registry = get_runtime_registry()
        
        self._heartbeat_interval = heartbeat_interval
        self._heartbeat_timeout = heartbeat_timeout
        self._degradation_threshold = degradation_threshold
        self._critical_threshold = critical_threshold
        
        self._health_checks: Dict[str, HealthCheck] = {}
        self._alerts: List[HealthAlert] = []
        self._max_alerts = 100
        
        self._alert_handlers: List[Callable] = []
        self._health_handlers: List[Callable] = []
        
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
        self._stats = {
            "total_checks": 0,
            "total_alerts": 0,
            "recovered": 0,
        }
        
        logger.info("RuntimeHealthSystem initialized")

    async def start(self) -> None:
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._health_check_loop())
        logger.info("RuntimeHealthSystem started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("RuntimeHealthSystem stopped")

    async def _health_check_loop(self) -> None:
        while self._running:
            try:
                await self._run_health_checks()
                await asyncio.sleep(self._heartbeat_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check loop error: {e}")
                await asyncio.sleep(1)

    async def _run_health_checks(self) -> None:
        runtimes = self._registry.get_all()
        
        for info in runtimes:
            await self._check_runtime(info)
        
        self._stats["total_checks"] += 1

    async def _check_runtime(self, info: Any) -> None:
        runtime_id = info.runtime_id
        
        try:
            healthy = True
            latency_ms = 0.0
            error = None
            metadata = {}
            
            if hasattr(info.instance, 'health_check'):
                start = datetime.fromtimestamp(now_ms() / 1000)
                try:
                    result = await info.instance.health_check()
                    latency_ms = (datetime.fromtimestamp(now_ms() / 1000) - start).total_seconds() * 1000
                    healthy = result.get("healthy", True)
                    error = result.get("error")
                    metadata = result.get("metadata", {})
                except Exception as e:
                    healthy = False
                    error = str(e)
                    latency_ms = self._critical_threshold
            
            status = self._determine_status(healthy, latency_ms, info.state)
            
            prev_check = self._health_checks.get(runtime_id)
            consecutive_failures = 0
            if prev_check:
                consecutive_failures = prev_check.consecutive_failures
                if not healthy:
                    consecutive_failures += 1
                else:
                    consecutive_failures = 0
            
            check = HealthCheck(
                runtime_id=runtime_id,
                status=status,
                latency_ms=latency_ms,
                last_heartbeat=datetime.fromtimestamp(now_ms() / 1000),
                consecutive_failures=consecutive_failures,
                error=error,
                metadata=metadata,
            )
            
            self._health_checks[runtime_id] = check
            
            if prev_check and prev_check.status != status:
                await self._handle_status_change(info, prev_check.status, status)
            
        except Exception as e:
            logger.error(f"Health check failed for {runtime_id}: {e}")

    def _determine_status(
        self,
        healthy: bool,
        latency_ms: float,
        runtime_state: RuntimeState,
    ) -> HealthStatus:
        if runtime_state == RuntimeState.FAILED:
            return HealthStatus.CRITICAL
        if runtime_state == RuntimeState.STOPPED:
            return HealthStatus.UNKNOWN
        if runtime_state == RuntimeState.DEGRADED:
            return HealthStatus.DEGRADED
        
        if not healthy:
            return HealthStatus.UNHEALTHY
        
        if latency_ms >= self._critical_threshold:
            return HealthStatus.CRITICAL
        if latency_ms >= self._degradation_threshold:
            return HealthStatus.DEGRADED
        
        return HealthStatus.HEALTHY

    async def _handle_status_change(
        self,
        info: Any,
        old_status: HealthStatus,
        new_status: HealthStatus,
    ) -> None:
        logger.info(f"Runtime {info.runtime_id} status changed: {old_status.value} -> {new_status.value}")
        
        if new_status in [HealthStatus.UNHEALTHY, HealthStatus.CRITICAL]:
            await self._create_alert(
                level=AlertLevel.ERROR if new_status == HealthStatus.UNHEALTHY else AlertLevel.CRITICAL,
                runtime_id=info.runtime_id,
                message=f"Runtime {info.runtime_id} is {new_status.value}",
            )
        
        for handler in self._health_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(info.runtime_id, old_status, new_status)
                else:
                    handler(info.runtime_id, old_status, new_status)
            except Exception as e:
                logger.error(f"Health handler error: {e}")

    async def _create_alert(
        self,
        level: AlertLevel,
        runtime_id: str,
        message: str,
    ) -> HealthAlert:
        import uuid
        alert = HealthAlert(
            alert_id=f"alert_{uuid.uuid4().hex[:8]}",
            level=level,
            runtime_id=runtime_id,
            message=message,
            timestamp=datetime.fromtimestamp(now_ms() / 1000),
        )
        
        self._alerts.append(alert)
        if len(self._alerts) > self._max_alerts:
            self._alerts = self._alerts[-self._max_alerts:]
        
        self._stats["total_alerts"] += 1
        
        for handler in self._alert_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(alert)
                else:
                    handler(alert)
            except Exception as e:
                logger.error(f"Alert handler error: {e}")
        
        return alert

    def get_health(self, runtime_id: str) -> Optional[HealthCheck]:
        return self._health_checks.get(runtime_id)

    def get_all_health(self) -> Dict[str, HealthCheck]:
        return self._health_checks.copy()

    def get_metrics(self) -> HealthMetrics:
        checks = list(self._health_checks.values())
        
        healthy = sum(1 for c in checks if c.status == HealthStatus.HEALTHY)
        degraded = sum(1 for c in checks if c.status == HealthStatus.DEGRADED)
        unhealthy = sum(1 for c in checks if c.status == HealthStatus.UNHEALTHY)
        critical = sum(1 for c in checks if c.status == HealthStatus.CRITICAL)
        
        latencies = [c.latency_ms for c in checks if c.latency_ms > 0]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        
        total = len(checks)
        uptime = (healthy / total * 100) if total > 0 else 100.0
        
        return HealthMetrics(
            total_runtimes=total,
            healthy_count=healthy,
            degraded_count=degraded,
            unhealthy_count=unhealthy,
            critical_count=critical,
            avg_latency_ms=avg_latency,
            uptime_percentage=uptime,
        )

    def get_alerts(self, limit: int = 20, unacknowledged_only: bool = False) -> List[HealthAlert]:
        alerts = self._alerts[-limit:]
        if unacknowledged_only:
            alerts = [a for a in alerts if not a.acknowledged]
        return alerts

    def acknowledge_alert(self, alert_id: str) -> bool:
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                return True
        return False

    def on_alert(self, handler: Callable) -> None:
        self._alert_handlers.append(handler)

    def on_health_change(self, handler: Callable) -> None:
        self._health_handlers.append(handler)

    def get_stats(self) -> Dict[str, Any]:
        metrics = self.get_metrics()
        return {
            "running": self._running,
            "metrics": {
                "total_runtimes": metrics.total_runtimes,
                "healthy": metrics.healthy_count,
                "degraded": metrics.degraded_count,
                "unhealthy": metrics.unhealthy_count,
                "critical": metrics.critical_count,
                "avg_latency_ms": metrics.avg_latency_ms,
                "uptime_percentage": metrics.uptime_percentage,
            },
            "stats": self._stats.copy(),
            "unacknowledged_alerts": len([a for a in self._alerts if not a.acknowledged]),
        }


def get_health_system() -> RuntimeHealthSystem:
    return RuntimeHealthSystem()
