"""
Runtime Governor - 总控制器

统一管理所有运行时组件:
- PriorityEventQueue: 优先级事件队列
- DegradationController: 推送降级控制器
- CircuitBreakerManager: 熔断器管理器
- SubscriptionManager: 订阅管理器

特性:
- 统一事件处理循环
- 负载监控
- 自动降级
- 健康检查
"""

import asyncio
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Callable, Awaitable, Set
from datetime import datetime
from enum import Enum
import time

from infrastructure.logging import get_logger
from infrastructure.runtime.priority_queue import (
    EventPriority,
    PrioritizedEvent,
    PriorityEventQueue,
)
from infrastructure.runtime.degradation import (
    RuntimeMode,
    DegradationController,
)
from infrastructure.runtime.circuit_breaker_manager import (
    CircuitBreakerManager,
    get_circuit_breaker_manager,
)
from infrastructure.runtime.subscription_manager import (
    SubscriptionManager,
)

logger = get_logger("runtime_governor.governor")


class GovernorState(Enum):
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"


@dataclass
class GovernorConfig:
    event_batch_size: int = 10
    event_loop_interval_ms: int = 1
    metrics_interval_seconds: float = 1.0
    cleanup_interval_seconds: float = 60.0
    health_check_interval_seconds: float = 5.0
    max_event_rate: int = 10000
    enable_auto_degradation: bool = True


class RuntimeGovernor:
    def __init__(self, config: Optional[GovernorConfig] = None):
        self.config = config or GovernorConfig()
        
        self.priority_queue = PriorityEventQueue()
        self.degradation = DegradationController(
            auto_adjust=self.config.enable_auto_degradation
        )
        self.circuit_breakers = get_circuit_breaker_manager()
        self.subscriptions = SubscriptionManager()
        
        self._state = GovernorState.STOPPED
        self._running = False
        self._tasks: Set[asyncio.Task] = set()
        
        self._event_handlers: Dict[str, Callable[[PrioritizedEvent], Awaitable[None]]] = {}
        self._event_rate_counter = 0
        self._event_rate_window_start = time.time()
        self._current_event_rate = 0.0
        
        self._stats = {
            "events_processed": 0,
            "events_dropped": 0,
            "errors": 0,
            "uptime_seconds": 0,
        }
        self._start_time: Optional[float] = None

    @property
    def state(self) -> GovernorState:
        return self._state

    @property
    def is_running(self) -> bool:
        return self._running and self._state == GovernorState.RUNNING

    def register_event_handler(
        self,
        event_type: str,
        handler: Callable[[PrioritizedEvent], Awaitable[None]],
    ) -> None:
        self._event_handlers[event_type] = handler
        logger.info(f"Registered event handler: {event_type}")

    def unregister_event_handler(self, event_type: str) -> None:
        self._event_handlers.pop(event_type, None)
        logger.info(f"Unregistered event handler: {event_type}")

    async def start(self) -> None:
        if self._running:
            logger.warning("RuntimeGovernor already running")
            return
        
        logger.info("Starting RuntimeGovernor...")
        self._state = GovernorState.INITIALIZING
        self._running = True
        self._start_time = time.time()
        
        self._tasks = {
            asyncio.create_task(self._event_loop()),
            asyncio.create_task(self._metrics_loop()),
            asyncio.create_task(self._cleanup_loop()),
            asyncio.create_task(self._health_check_loop()),
        }
        
        self._state = GovernorState.RUNNING
        logger.info("RuntimeGovernor started")

    async def stop(self) -> None:
        if not self._running:
            return
        
        logger.info("Stopping RuntimeGovernor...")
        self._state = GovernorState.STOPPING
        self._running = False
        
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self._tasks.clear()
        self._state = GovernorState.STOPPED
        
        if self._start_time:
            self._stats["uptime_seconds"] = time.time() - self._start_time
        
        logger.info(f"RuntimeGovernor stopped. Stats: {self._stats}")

    async def pause(self) -> None:
        if self._state == GovernorState.RUNNING:
            self._state = GovernorState.PAUSED
            logger.info("RuntimeGovernor paused")

    async def resume(self) -> None:
        if self._state == GovernorState.PAUSED:
            self._state = GovernorState.RUNNING
            logger.info("RuntimeGovernor resumed")

    async def push_event(self, event: PrioritizedEvent) -> bool:
        if self.degradation.should_drop_event(event.priority):
            self._stats["events_dropped"] += 1
            return False
        
        if not self.degradation.should_process_event(event.event_type):
            self._stats["events_dropped"] += 1
            return False
        
        return await self.priority_queue.push(event)

    def push_event_nowait(self, event: PrioritizedEvent) -> bool:
        if self.degradation.should_drop_event(event.priority):
            self._stats["events_dropped"] += 1
            return False
        
        if not self.degradation.should_process_event(event.event_type):
            self._stats["events_dropped"] += 1
            return False
        
        return self.priority_queue.push_nowait(event)

    async def _event_loop(self) -> None:
        logger.info("Event loop started")
        
        while self._running:
            if self._state == GovernorState.PAUSED:
                await asyncio.sleep(0.1)
                continue
            
            try:
                event = await self.priority_queue.pop(
                    timeout=self.config.event_loop_interval_ms / 1000
                )
                
                if event:
                    await self._process_event(event)
                
            except Exception as e:
                logger.error(f"Event loop error: {e}")
                self._stats["errors"] += 1
                await asyncio.sleep(0.1)
        
        logger.info("Event loop stopped")

    async def _process_event(self, event: PrioritizedEvent) -> None:
        self._update_event_rate()
        
        if self._current_event_rate > self.config.max_event_rate:
            if event.priority > EventPriority.P1_HIGH:
                self._stats["events_dropped"] += 1
                return
        
        handler = self._event_handlers.get(event.event_type)
        
        if handler:
            try:
                await handler(event)
                self._stats["events_processed"] += 1
            except Exception as e:
                logger.error(f"Error processing event {event.event_type}: {e}")
                self._stats["errors"] += 1
        else:
            await self._default_event_handler(event)
            self._stats["events_processed"] += 1

    async def _default_event_handler(self, event: PrioritizedEvent) -> None:
        pass

    def _update_event_rate(self) -> None:
        now = time.time()
        self._event_rate_counter += 1
        
        window = now - self._event_rate_window_start
        if window >= 1.0:
            self._current_event_rate = self._event_rate_counter / window
            self._event_rate_counter = 0
            self._event_rate_window_start = now

    async def _metrics_loop(self) -> None:
        logger.info("Metrics loop started")
        
        while self._running:
            try:
                metrics = await self._collect_metrics()
                await self.degradation.update_load_metrics(metrics)
                
                if self._start_time:
                    self._stats["uptime_seconds"] = time.time() - self._start_time
                
            except Exception as e:
                logger.error(f"Metrics loop error: {e}")
            
            await asyncio.sleep(self.config.metrics_interval_seconds)
        
        logger.info("Metrics loop stopped")

    async def _collect_metrics(self) -> Dict[str, Any]:
        metrics = {
            "queue_lag": self.priority_queue.size(),
            "event_rate": self._current_event_rate,
        }
        
        try:
            import psutil
            metrics["cpu"] = psutil.cpu_percent()
            metrics["memory"] = psutil.virtual_memory().percent
        except ImportError:
            metrics["cpu"] = 0.0
            metrics["memory"] = 0.0
        except Exception:
            metrics["cpu"] = 0.0
            metrics["memory"] = 0.0
        
        return metrics

    async def _cleanup_loop(self) -> None:
        logger.info("Cleanup loop started")
        
        while self._running:
            try:
                removed = await self.subscriptions.cleanup_inactive()
                if removed > 0:
                    logger.info(f"Cleaned up {removed} inactive subscriptions")
                
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")
            
            await asyncio.sleep(self.config.cleanup_interval_seconds)
        
        logger.info("Cleanup loop stopped")

    async def _health_check_loop(self) -> None:
        logger.info("Health check loop started")
        
        while self._running:
            try:
                open_circuits = self.circuit_breakers.get_open_circuits()
                if open_circuits:
                    logger.warning(f"Open circuits: {open_circuits}")
                
                if not self.circuit_breakers.is_healthy():
                    logger.warning("System unhealthy due to open critical circuits")
                
            except Exception as e:
                logger.error(f"Health check loop error: {e}")
            
            await asyncio.sleep(self.config.health_check_interval_seconds)
        
        logger.info("Health check loop stopped")

    async def set_mode(self, mode: RuntimeMode, reason: str = "manual") -> None:
        await self.degradation.set_mode(mode, reason)

    def get_mode(self) -> RuntimeMode:
        return self.degradation.mode

    def get_stats(self) -> Dict[str, Any]:
        return {
            "state": self._state.value,
            "governor_stats": self._stats,
            "event_rate": self._current_event_rate,
            "queue_stats": self.priority_queue.get_stats(),
            "degradation_stats": self.degradation.get_stats(),
            "circuit_breaker_stats": self.circuit_breakers.get_all_stats(),
            "subscription_stats": self.subscriptions.get_stats(),
        }

    def is_healthy(self) -> bool:
        if not self.is_running:
            return False
        
        if not self.circuit_breakers.is_healthy():
            return False
        
        if self.degradation.mode == RuntimeMode.CRITICAL:
            return False
        
        return True

    async def force_recovery(self) -> None:
        logger.info("Forcing recovery mode...")
        
        await self.set_mode(RuntimeMode.RECOVERY, "force_recovery")
        
        self.circuit_breakers.reset_all()
        
        self.priority_queue.clear()
        
        logger.info("Recovery completed, transitioning to NORMAL mode")
        await self.set_mode(RuntimeMode.NORMAL, "recovery_complete")


_governor: Optional[RuntimeGovernor] = None


def get_runtime_governor(config: Optional[GovernorConfig] = None) -> RuntimeGovernor:
    global _governor
    if _governor is None:
        _governor = RuntimeGovernor(config)
    return _governor
