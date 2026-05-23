"""
Runtime Supervisor - Runtime 守护器

核心职责:
1. 监控 runtime 健康状态
2. 自动恢复崩溃的 runtime
3. 熔断保护
4. 告警通知
"""
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import asyncio

from .registry import RuntimeState, RuntimeInfo, get_runtime_registry
from .lifecycle import get_runtime_lifecycle
from infrastructure.logging import get_logger

logger = get_logger("runtime.supervisor")


@dataclass
class SupervisionConfig:
    check_interval: float = 5.0
    max_recovery_attempts: int = 3
    recovery_cooldown: float = 30.0
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: float = 60.0


@dataclass
class RuntimeHealth:
    runtime_id: str
    healthy: bool
    last_check: datetime
    consecutive_failures: int
    last_error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CircuitBreakerState:
    is_open: bool
    failure_count: int
    last_failure: Optional[datetime] = None
    open_since: Optional[datetime] = None


class RuntimeSupervisor:
    _instance: Optional['RuntimeSupervisor'] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config: Optional[SupervisionConfig] = None):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._initialized = True
        self._config = config or SupervisionConfig()
        
        self._registry = get_runtime_registry()
        self._lifecycle = get_runtime_lifecycle()
        
        self._health_status: Dict[str, RuntimeHealth] = {}
        self._recovery_attempts: Dict[str, int] = {}
        self._last_recovery: Dict[str, datetime] = {}
        self._circuit_breakers: Dict[str, CircuitBreakerState] = {}
        
        self._alert_handlers: List[Callable] = []
        
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
        self._stats = {
            "total_checks": 0,
            "total_recoveries": 0,
            "successful_recoveries": 0,
            "failed_recoveries": 0,
            "circuit_breaker_trips": 0,
        }
        
        logger.info("RuntimeSupervisor initialized")

    async def start(self) -> None:
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._supervision_loop())
        logger.info("RuntimeSupervisor started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("RuntimeSupervisor stopped")

    async def _supervision_loop(self) -> None:
        while self._running:
            try:
                await self._check_all_runtimes()
                await asyncio.sleep(self._config.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Supervision loop error: {e}")
                await asyncio.sleep(5)

    async def _check_all_runtimes(self) -> None:
        runtimes = self._registry.get_active()
        
        for info in runtimes:
            await self._check_runtime(info)
        
        self._stats["total_checks"] += 1

    async def _check_runtime(self, info: RuntimeInfo) -> None:
        runtime_id = info.runtime_id
        
        if self._is_circuit_breaker_open(runtime_id):
            return
        
        try:
            healthy = True
            health_data = {}
            
            if hasattr(info.instance, 'health_check'):
                result = await info.instance.health_check()
                healthy = result.get("healthy", True)
                health_data = result
            
            if runtime_id not in self._health_status:
                self._health_status[runtime_id] = RuntimeHealth(
                    runtime_id=runtime_id,
                    healthy=healthy,
                    last_check=datetime.fromtimestamp(now_ms() / 1000),
                    consecutive_failures=0,
                )
            else:
                health = self._health_status[runtime_id]
                health.healthy = healthy
                health.last_check = datetime.fromtimestamp(now_ms() / 1000)
                health.metadata = health_data
                
                if not healthy:
                    health.consecutive_failures += 1
                    await self._handle_unhealthy(info, health)
                else:
                    health.consecutive_failures = 0
                    health.last_error = None
                    
        except Exception as e:
            logger.error(f"Health check failed for {runtime_id}: {e}")
            
            if runtime_id in self._health_status:
                self._health_status[runtime_id].consecutive_failures += 1
                self._health_status[runtime_id].last_error = str(e)
            
            await self._handle_failure(info, str(e))

    async def _handle_unhealthy(self, info: RuntimeInfo, health: RuntimeHealth) -> None:
        logger.warning(f"Runtime {info.runtime_id} unhealthy (failures: {health.consecutive_failures})")
        
        await self._send_alert("warning", info.runtime_id, f"Runtime unhealthy: {health.last_error}")
        
        if health.consecutive_failures >= self._config.circuit_breaker_threshold:
            await self._trip_circuit_breaker(info.runtime_id)
        else:
            await self._attempt_recovery(info)

    async def _handle_failure(self, info: RuntimeInfo, error: str) -> None:
        logger.error(f"Runtime {info.runtime_id} failure: {error}")
        
        await self._send_alert("error", info.runtime_id, f"Runtime failure: {error}")
        
        await self._attempt_recovery(info)

    async def _attempt_recovery(self, info: RuntimeInfo) -> None:
        runtime_id = info.runtime_id
        
        if self._is_circuit_breaker_open(runtime_id):
            return
        
        attempts = self._recovery_attempts.get(runtime_id, 0)
        if attempts >= self._config.max_recovery_attempts:
            logger.warning(f"Max recovery attempts reached for {runtime_id}")
            await self._trip_circuit_breaker(runtime_id)
            return
        
        last_recovery = self._last_recovery.get(runtime_id)
        if last_recovery:
            elapsed = (datetime.fromtimestamp(now_ms() / 1000) - last_recovery).total_seconds()
            if elapsed < self._config.recovery_cooldown:
                return
        
        logger.info(f"Attempting recovery for {runtime_id} (attempt {attempts + 1})")
        
        self._recovery_attempts[runtime_id] = attempts + 1
        self._stats["total_recoveries"] += 1
        
        success = await self._lifecycle.recover(runtime_id)
        
        if success:
            try:
                from runtime.recovery import get_runtime_recovery
                recovery = get_runtime_recovery()
                info_obj = self._registry.get(runtime_id)
                runtime_name = info_obj.runtime_type.value if info_obj else None
                await recovery.recover_runtime(runtime_id, runtime_name=runtime_name)
            except Exception as e:
                logger.debug(f"Event replay recovery skipped for {runtime_id}: {e}")

            self._stats["successful_recoveries"] += 1
            self._recovery_attempts[runtime_id] = 0
            self._last_recovery[runtime_id] = datetime.fromtimestamp(now_ms() / 1000)
            await self._send_alert("info", runtime_id, "Runtime recovered successfully")
        else:
            self._stats["failed_recoveries"] += 1

    async def _trip_circuit_breaker(self, runtime_id: str) -> None:
        if runtime_id not in self._circuit_breakers:
            self._circuit_breakers[runtime_id] = CircuitBreakerState(
                is_open=False,
                failure_count=0,
            )
        
        cb = self._circuit_breakers[runtime_id]
        cb.is_open = True
        cb.open_since = datetime.fromtimestamp(now_ms() / 1000)
        cb.failure_count += 1
        
        self._stats["circuit_breaker_trips"] += 1
        
        logger.warning(f"Circuit breaker tripped for {runtime_id}")
        await self._send_alert("critical", runtime_id, "Circuit breaker tripped - runtime disabled")

    def _is_circuit_breaker_open(self, runtime_id: str) -> bool:
        if runtime_id not in self._circuit_breakers:
            return False
        
        cb = self._circuit_breakers[runtime_id]
        if not cb.is_open:
            return False
        
        if cb.open_since:
            elapsed = (datetime.fromtimestamp(now_ms() / 1000) - cb.open_since).total_seconds()
            if elapsed >= self._config.circuit_breaker_timeout:
                cb.is_open = False
                logger.info(f"Circuit breaker reset for {runtime_id}")
                return False
        
        return True

    def reset_circuit_breaker(self, runtime_id: str) -> None:
        if runtime_id in self._circuit_breakers:
            self._circuit_breakers[runtime_id].is_open = False
            self._recovery_attempts[runtime_id] = 0
            logger.info(f"Circuit breaker manually reset for {runtime_id}")

    async def _send_alert(self, level: str, runtime_id: str, message: str) -> None:
        alert = {
            "level": level,
            "runtime_id": runtime_id,
            "message": message,
            "timestamp": datetime.fromtimestamp(now_ms() / 1000).isoformat(),
        }
        
        for handler in self._alert_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(alert)
                else:
                    handler(alert)
            except Exception as e:
                logger.error(f"Alert handler error: {e}")

    def on_alert(self, handler: Callable) -> None:
        self._alert_handlers.append(handler)

    def get_health(self, runtime_id: Optional[str] = None) -> Dict[str, Any]:
        if runtime_id:
            health = self._health_status.get(runtime_id)
            return health.__dict__ if health else {}
        
        return {
            rid: health.__dict__
            for rid, health in self._health_status.items()
        }

    def get_circuit_breakers(self) -> Dict[str, Any]:
        return {
            rid: {
                "is_open": cb.is_open,
                "failure_count": cb.failure_count,
                "open_since": cb.open_since.isoformat() if cb.open_since else None,
            }
            for rid, cb in self._circuit_breakers.items()
        }

    def get_stats(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "stats": self._stats.copy(),
            "circuit_breakers": self.get_circuit_breakers(),
        }


def get_runtime_supervisor() -> RuntimeSupervisor:
    return RuntimeSupervisor()
