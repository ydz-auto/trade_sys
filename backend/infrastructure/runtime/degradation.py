"""
Degradation Controller - 推送降级控制器

Runtime Modes:
- NORMAL: 全功能
- DEGRADED: 降低刷新率
- SAFE_MODE: 关闭 AI/replay
- CRITICAL: 只保留交易核心
- READ_ONLY: 禁止下单
- RECOVERY: 重建状态

特性:
- 根据系统负载自动切换模式
- 不同模式下的推送频率控制
- 事件过滤（低优先级事件在高压时丢弃）
"""

import asyncio
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Callable
from datetime import datetime
import time

from infrastructure.logging import get_logger
from infrastructure.runtime.priority_queue import EventPriority

logger = get_logger("runtime_governor.degradation")


class RuntimeMode(Enum):
    NORMAL = "normal"
    DEGRADED = "degraded"
    SAFE_MODE = "safe_mode"
    CRITICAL = "critical"
    READ_ONLY = "read_only"
    RECOVERY = "recovery"

    def __str__(self) -> str:
        return self.value


@dataclass
class DegradationConfig:
    tick_interval_ms: int = 100
    risk_interval_ms: int = 500
    factor_interval_ms: int = 1000
    signal_interval_ms: int = 1000
    position_interval_ms: int = 500
    news_interval_ms: int = 5000
    ai_enabled: bool = True
    replay_enabled: bool = True
    full_dashboard: bool = True
    max_events_per_second: int = 1000
    batch_size: int = 10

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tick_interval_ms": self.tick_interval_ms,
            "risk_interval_ms": self.risk_interval_ms,
            "factor_interval_ms": self.factor_interval_ms,
            "signal_interval_ms": self.signal_interval_ms,
            "position_interval_ms": self.position_interval_ms,
            "news_interval_ms": self.news_interval_ms,
            "ai_enabled": self.ai_enabled,
            "replay_enabled": self.replay_enabled,
            "full_dashboard": self.full_dashboard,
            "max_events_per_second": self.max_events_per_second,
            "batch_size": self.batch_size,
        }


DEGRADATION_PROFILES: Dict[RuntimeMode, DegradationConfig] = {
    RuntimeMode.NORMAL: DegradationConfig(
        tick_interval_ms=100,
        risk_interval_ms=500,
        factor_interval_ms=1000,
        signal_interval_ms=1000,
        position_interval_ms=500,
        news_interval_ms=5000,
        ai_enabled=True,
        replay_enabled=True,
        full_dashboard=True,
        max_events_per_second=1000,
        batch_size=10,
    ),
    RuntimeMode.DEGRADED: DegradationConfig(
        tick_interval_ms=500,
        risk_interval_ms=2000,
        factor_interval_ms=5000,
        signal_interval_ms=3000,
        position_interval_ms=1000,
        news_interval_ms=10000,
        ai_enabled=True,
        replay_enabled=False,
        full_dashboard=False,
        max_events_per_second=500,
        batch_size=20,
    ),
    RuntimeMode.SAFE_MODE: DegradationConfig(
        tick_interval_ms=1000,
        risk_interval_ms=5000,
        factor_interval_ms=10000,
        signal_interval_ms=5000,
        position_interval_ms=2000,
        news_interval_ms=30000,
        ai_enabled=False,
        replay_enabled=False,
        full_dashboard=False,
        max_events_per_second=200,
        batch_size=50,
    ),
    RuntimeMode.CRITICAL: DegradationConfig(
        tick_interval_ms=100,
        risk_interval_ms=1000,
        factor_interval_ms=60000,
        signal_interval_ms=60000,
        position_interval_ms=500,
        news_interval_ms=60000,
        ai_enabled=False,
        replay_enabled=False,
        full_dashboard=False,
        max_events_per_second=100,
        batch_size=5,
    ),
    RuntimeMode.READ_ONLY: DegradationConfig(
        tick_interval_ms=500,
        risk_interval_ms=2000,
        factor_interval_ms=5000,
        signal_interval_ms=5000,
        position_interval_ms=2000,
        news_interval_ms=10000,
        ai_enabled=False,
        replay_enabled=True,
        full_dashboard=False,
        max_events_per_second=300,
        batch_size=20,
    ),
    RuntimeMode.RECOVERY: DegradationConfig(
        tick_interval_ms=1000,
        risk_interval_ms=1000,
        factor_interval_ms=10000,
        signal_interval_ms=10000,
        position_interval_ms=1000,
        news_interval_ms=60000,
        ai_enabled=False,
        replay_enabled=False,
        full_dashboard=False,
        max_events_per_second=50,
        batch_size=10,
    ),
}


@dataclass
class LoadMetrics:
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    queue_lag: int = 0
    websocket_connections: int = 0
    event_rate: float = 0.0
    error_rate: float = 0.0
    latency_p99_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cpu_percent": self.cpu_percent,
            "memory_percent": self.memory_percent,
            "queue_lag": self.queue_lag,
            "websocket_connections": self.websocket_connections,
            "event_rate": self.event_rate,
            "error_rate": self.error_rate,
            "latency_p99_ms": self.latency_p99_ms,
            "timestamp": self.timestamp,
        }


class DegradationController:
    def __init__(
        self,
        initial_mode: RuntimeMode = RuntimeMode.NORMAL,
        auto_adjust: bool = True,
    ):
        self._current_mode = initial_mode
        self._config = DEGRADATION_PROFILES[initial_mode]
        self._auto_adjust = auto_adjust
        self._load_metrics = LoadMetrics()
        self._mode_history: list[tuple[RuntimeMode, float, str]] = []
        self._last_mode_change = time.time()
        self._min_mode_duration = 5.0
        self._lock = asyncio.Lock()
        
        self._thresholds = {
            "cpu_critical": 90,
            "cpu_safe": 80,
            "cpu_degraded": 70,
            "queue_critical": 10000,
            "queue_safe": 5000,
            "queue_degraded": 1000,
            "error_critical": 0.5,
            "error_safe": 0.2,
            "latency_critical": 5000,
            "latency_safe": 2000,
        }
        
        self._on_mode_change_callbacks: list[Callable[[RuntimeMode, RuntimeMode], None]] = []

    @property
    def mode(self) -> RuntimeMode:
        return self._current_mode

    @property
    def config(self) -> DegradationConfig:
        return self._config

    @property
    def load_metrics(self) -> LoadMetrics:
        return self._load_metrics

    def register_mode_change_callback(
        self,
        callback: Callable[[RuntimeMode, RuntimeMode], None],
    ):
        self._on_mode_change_callbacks.append(callback)

    async def update_load_metrics(self, metrics: Dict[str, Any]) -> None:
        self._load_metrics = LoadMetrics(
            cpu_percent=metrics.get("cpu", self._load_metrics.cpu_percent),
            memory_percent=metrics.get("memory", self._load_metrics.memory_percent),
            queue_lag=metrics.get("queue_lag", self._load_metrics.queue_lag),
            websocket_connections=metrics.get(
                "ws_connections", self._load_metrics.websocket_connections
            ),
            event_rate=metrics.get("event_rate", self._load_metrics.event_rate),
            error_rate=metrics.get("error_rate", self._load_metrics.error_rate),
            latency_p99_ms=metrics.get("latency_p99", self._load_metrics.latency_p99_ms),
        )
        
        if self._auto_adjust:
            await self._auto_adjust_mode()

    def update_load_metrics_sync(self, metrics: Dict[str, Any]) -> None:
        self._load_metrics = LoadMetrics(
            cpu_percent=metrics.get("cpu", self._load_metrics.cpu_percent),
            memory_percent=metrics.get("memory", self._load_metrics.memory_percent),
            queue_lag=metrics.get("queue_lag", self._load_metrics.queue_lag),
            websocket_connections=metrics.get(
                "ws_connections", self._load_metrics.websocket_connections
            ),
            event_rate=metrics.get("event_rate", self._load_metrics.event_rate),
            error_rate=metrics.get("error_rate", self._load_metrics.error_rate),
            latency_p99_ms=metrics.get("latency_p99", self._load_metrics.latency_p99_ms),
        )
        
        if self._auto_adjust:
            self._auto_adjust_mode_sync()

    async def _auto_adjust_mode(self) -> None:
        async with self._lock:
            self._do_auto_adjust()

    def _auto_adjust_mode_sync(self) -> None:
        self._do_auto_adjust()

    def _do_auto_adjust(self) -> None:
        if time.time() - self._last_mode_change < self._min_mode_duration:
            return
        
        metrics = self._load_metrics
        t = self._thresholds
        
        critical_score = 0
        if metrics.cpu_percent > t["cpu_critical"]:
            critical_score += 3
        elif metrics.cpu_percent > t["cpu_safe"]:
            critical_score += 2
        elif metrics.cpu_percent > t["cpu_degraded"]:
            critical_score += 1
        
        if metrics.queue_lag > t["queue_critical"]:
            critical_score += 3
        elif metrics.queue_lag > t["queue_safe"]:
            critical_score += 2
        elif metrics.queue_lag > t["queue_degraded"]:
            critical_score += 1
        
        if metrics.error_rate > t["error_critical"]:
            critical_score += 2
        elif metrics.error_rate > t["error_safe"]:
            critical_score += 1
        
        if metrics.latency_p99_ms > t["latency_critical"]:
            critical_score += 2
        elif metrics.latency_p99_ms > t["latency_safe"]:
            critical_score += 1
        
        new_mode = RuntimeMode.NORMAL
        if critical_score >= 6:
            new_mode = RuntimeMode.CRITICAL
        elif critical_score >= 4:
            new_mode = RuntimeMode.SAFE_MODE
        elif critical_score >= 2:
            new_mode = RuntimeMode.DEGRADED
        
        if new_mode != self._current_mode:
            self._set_mode(new_mode, "auto_adjust")

    async def set_mode(self, mode: RuntimeMode, reason: str = "manual") -> None:
        async with self._lock:
            self._set_mode(mode, reason)

    def _set_mode(self, mode: RuntimeMode, reason: str) -> None:
        if mode == self._current_mode:
            return
        
        old_mode = self._current_mode
        self._current_mode = mode
        self._config = DEGRADATION_PROFILES[mode]
        self._last_mode_change = time.time()
        
        self._mode_history.append((mode, time.time(), reason))
        if len(self._mode_history) > 100:
            self._mode_history = self._mode_history[-100:]
        
        logger.info(
            f"Runtime mode changed: {old_mode.value} -> {mode.value} "
            f"(reason={reason})"
        )
        
        for callback in self._on_mode_change_callbacks:
            try:
                callback(old_mode, mode)
            except Exception as e:
                logger.error(f"Mode change callback error: {e}")

    def should_drop_event(self, priority: EventPriority) -> bool:
        if self._current_mode == RuntimeMode.CRITICAL:
            return priority > EventPriority.P1_HIGH
        if self._current_mode == RuntimeMode.SAFE_MODE:
            return priority > EventPriority.P2_NORMAL
        if self._current_mode == RuntimeMode.DEGRADED:
            return priority > EventPriority.P3_LOW
        return False

    def should_process_event(self, event_type: str) -> bool:
        config = self._config
        
        if event_type in ("ai_summary", "ai_analysis", "ai_prediction"):
            return config.ai_enabled
        
        if event_type in ("replay", "replay_tick", "replay_snapshot"):
            return config.replay_enabled
        
        if self._current_mode == RuntimeMode.READ_ONLY:
            if event_type in ("order", "execute", "trade"):
                return False
        
        return True

    def get_interval_ms(self, event_type: str) -> int:
        config = self._config
        
        interval_map = {
            "tick": config.tick_interval_ms,
            "price": config.tick_interval_ms,
            "risk": config.risk_interval_ms,
            "factor": config.factor_interval_ms,
            "signal": config.signal_interval_ms,
            "position": config.position_interval_ms,
            "news": config.news_interval_ms,
        }
        
        return interval_map.get(event_type, 1000)

    def get_throttle_key(self, event_type: str) -> str:
        interval_ms = self.get_interval_ms(event_type)
        bucket = int(time.time() * 1000 / interval_ms)
        return f"{event_type}:{bucket}"

    def get_stats(self) -> Dict[str, Any]:
        return {
            "current_mode": self._current_mode.value,
            "config": self._config.to_dict(),
            "load_metrics": self._load_metrics.to_dict(),
            "mode_history": [
                {"mode": m.value, "time": t, "reason": r}
                for m, t, r in self._mode_history[-10:]
            ],
            "auto_adjust": self._auto_adjust,
            "thresholds": self._thresholds,
        }

    def reset(self) -> None:
        self._current_mode = RuntimeMode.NORMAL
        self._config = DEGRADATION_PROFILES[RuntimeMode.NORMAL]
        self._load_metrics = LoadMetrics()
        self._mode_history.clear()
        self._last_mode_change = time.time()
