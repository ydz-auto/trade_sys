"""
Observability Manager - 可观测性统一管理器

统一管理：
1. Prometheus 指标
2. OpenTelemetry 追踪
3. 事件丢失检测
4. Consumer Lag 监控
5. 健康检查
6. 告警
"""

import time
from typing import Dict, Optional, Any
from dataclasses import dataclass, field

from infrastructure.logging import get_logger
from infrastructure.monitoring.metrics import metrics_collector, MetricsCollector
from infrastructure.monitoring.health import HealthChecker
from infrastructure.observability.event_loss import EventLossDetector
from infrastructure.observability.lag_monitor import ConsumerLagMonitor
from shared.config.defaults.infrastructure.middleware import KAFKA_BOOTSTRAP_SERVERS

logger = get_logger("infrastructure.observability.manager")


@dataclass
class ObservabilityConfig:
    """可观测性配置"""
    prometheus_port: int = 9090
    enable_prometheus: bool = True
    enable_tracing: bool = True
    otlp_endpoint: str = "localhost:4317"
    service_name: str = "tradeagent"
    enable_event_loss_detection: bool = True
    enable_lag_monitor: bool = True
    kafka_bootstrap_servers: str = field(default_factory=lambda: KAFKA_BOOTSTRAP_SERVERS)


class ObservabilityManager:
    """可观测性统一管理器
    
    统一管理：
    1. Prometheus 指标
    2. OpenTelemetry 追踪
    3. 事件丢失检测
    4. Consumer Lag 监控
    5. 健康检查
    6. 告警
    """

    def __init__(self, config: Optional[ObservabilityConfig] = None):
        self.config = config or ObservabilityConfig()
        self.prometheus = None
        self.tracing = None
        self.event_loss_detector: Optional[EventLossDetector] = None
        self.lag_monitor: Optional[ConsumerLagMonitor] = None
        self.health_checker: Optional[HealthChecker] = None
        self._running = False
        self._start_time: Optional[float] = None

    async def initialize(self) -> None:
        if self.config.enable_prometheus:
            try:
                from infrastructure.observability.prometheus_server import PrometheusMetricsServer
                self.prometheus = PrometheusMetricsServer(
                    port=self.config.prometheus_port,
                    metrics_collector=metrics_collector,
                )
                await self.prometheus.initialize()
                logger.info("Prometheus metrics server initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Prometheus: {e}")

        if self.config.enable_tracing:
            try:
                from infrastructure.observability.tracing import TracingManager
                self.tracing = TracingManager(
                    service_name=self.config.service_name,
                    otlp_endpoint=self.config.otlp_endpoint,
                )
                await self.tracing.initialize()
                logger.info("Tracing manager initialized")
            except Exception as e:
                logger.error(f"Failed to initialize tracing: {e}")

        if self.config.enable_event_loss_detection:
            try:
                self.event_loss_detector = EventLossDetector()
                logger.info("Event loss detector initialized")
            except Exception as e:
                logger.error(f"Failed to initialize event loss detector: {e}")

        if self.config.enable_lag_monitor:
            try:
                self.lag_monitor = ConsumerLagMonitor(
                    bootstrap_servers=self.config.kafka_bootstrap_servers,
                )
                logger.info("Lag monitor initialized")
            except Exception as e:
                logger.error(f"Failed to initialize lag monitor: {e}")

        self.health_checker = HealthChecker()
        logger.info("Observability manager initialized")

    async def start(self) -> None:
        self._start_time = time.time()

        if self.prometheus:
            try:
                await self.prometheus.start()
            except Exception as e:
                logger.error(f"Failed to start Prometheus: {e}")

        if self.event_loss_detector:
            try:
                await self.event_loss_detector.start()
            except Exception as e:
                logger.error(f"Failed to start event loss detector: {e}")

        if self.lag_monitor:
            try:
                await self.lag_monitor.start()
            except Exception as e:
                logger.error(f"Failed to start lag monitor: {e}")

        self._running = True
        logger.info("Observability manager started")

    async def stop(self) -> None:
        self._running = False

        if self.prometheus:
            try:
                await self.prometheus.stop()
            except Exception as e:
                logger.error(f"Error stopping Prometheus: {e}")

        if self.tracing:
            try:
                await self.tracing.shutdown()
            except Exception as e:
                logger.error(f"Error shutting down tracing: {e}")

        if self.event_loss_detector:
            try:
                await self.event_loss_detector.stop()
            except Exception as e:
                logger.error(f"Error stopping event loss detector: {e}")

        if self.lag_monitor:
            try:
                await self.lag_monitor.stop()
            except Exception as e:
                logger.error(f"Error stopping lag monitor: {e}")

        logger.info("Observability manager stopped")

    async def record_event_processed(self, event_type: str, service: str, latency_ms: float) -> None:
        metrics_collector.increment(
            f"{service}.events_processed",
            tags={"event_type": event_type},
        )
        metrics_collector.observe(
            f"{service}.event_latency_ms",
            latency_ms,
            tags={"event_type": event_type},
        )

        if self.prometheus:
            try:
                self.prometheus.increment_counter(
                    "tradeagent_pipeline_events_total",
                    labels={"stage": service, "event_type": event_type, "status": "success"},
                )
                self.prometheus.observe_histogram(
                    "tradeagent_system_event_processing_ms",
                    latency_ms,
                    labels={"event_type": event_type},
                )
            except Exception:
                pass

    async def record_event_error(self, event_type: str, service: str, error_type: str) -> None:
        metrics_collector.increment(
            f"{service}.errors",
            tags={"event_type": event_type, "error_type": error_type},
        )

        if self.prometheus:
            try:
                self.prometheus.increment_counter(
                    "tradeagent_pipeline_events_total",
                    labels={"stage": service, "event_type": event_type, "status": "error"},
                )
                self.prometheus.increment_counter(
                    "tradeagent_system_errors_total",
                    labels={"type": error_type, "module": service},
                )
            except Exception:
                pass

    async def record_trading_metric(self, metric_name: str, value: float, labels: Optional[Dict] = None) -> None:
        metrics_collector.set_gauge(metric_name, value, tags=labels or {})

        if self.prometheus:
            try:
                if metric_name in self.prometheus._custom_metrics:
                    self.prometheus.set_gauge(metric_name, value, labels=labels)
            except Exception:
                pass

    async def record_pipeline_latency(self, stage: str, latency_ms: float) -> None:
        metrics_collector.observe(
            "pipeline.stage_latency_ms",
            latency_ms,
            tags={"stage": stage},
        )

        if self.prometheus:
            try:
                self.prometheus.observe_histogram(
                    "tradeagent_pipeline_stage_latency_ms",
                    latency_ms,
                    labels={"stage": stage},
                )
            except Exception:
                pass

    async def get_status(self) -> Dict[str, Any]:
        status = {
            "running": self._running,
            "uptime_seconds": time.time() - self._start_time if self._start_time else 0,
            "components": {
                "prometheus": {
                    "enabled": self.config.enable_prometheus,
                    "running": self.prometheus.is_running if self.prometheus else False,
                    "port": self.config.prometheus_port,
                },
                "tracing": {
                    "enabled": self.config.enable_tracing,
                    "initialized": self.tracing.is_initialized if self.tracing else False,
                    "endpoint": self.config.otlp_endpoint,
                },
                "event_loss_detector": {
                    "enabled": self.config.enable_event_loss_detection,
                    "active": self.event_loss_detector is not None,
                },
                "lag_monitor": {
                    "enabled": self.config.enable_lag_monitor,
                    "active": self.lag_monitor is not None,
                },
                "health_checker": {
                    "active": self.health_checker is not None,
                },
            },
        }

        if self.event_loss_detector:
            stats = self.event_loss_detector.get_stats()
            status["event_loss_stats"] = stats.to_dict()

        if self.lag_monitor:
            status["lag_stats"] = self.lag_monitor.get_stats()

        return status

    async def health_check(self) -> Dict[str, Any]:
        result = {
            "status": "healthy",
            "timestamp": time.time(),
            "components": {},
        }

        components_healthy = True

        if self.prometheus:
            prom_healthy = self.prometheus.is_running
            result["components"]["prometheus"] = {
                "status": "healthy" if prom_healthy else "unhealthy",
                "port": self.config.prometheus_port,
            }
            if not prom_healthy:
                components_healthy = False

        if self.tracing:
            trace_healthy = self.tracing.is_initialized
            result["components"]["tracing"] = {
                "status": "healthy" if trace_healthy else "unhealthy",
                "endpoint": self.config.otlp_endpoint,
            }
            if not trace_healthy:
                components_healthy = False

        if self.event_loss_detector:
            result["components"]["event_loss_detector"] = {"status": "healthy"}

        if self.lag_monitor:
            result["components"]["lag_monitor"] = {"status": "healthy"}

        if self.health_checker:
            try:
                overall = await self.health_checker.get_overall_status()
                result["components"]["health_checks"] = overall
                if overall.get("overall") != "OK":
                    components_healthy = False
            except Exception as e:
                result["components"]["health_checks"] = {"status": "error", "error": str(e)}
                components_healthy = False

        if not components_healthy:
            result["status"] = "degraded"

        return result


_observability_manager: Optional[ObservabilityManager] = None


async def get_observability_manager(config: Optional[ObservabilityConfig] = None) -> ObservabilityManager:
    """获取可观测性管理器实例"""
    global _observability_manager
    if _observability_manager is None:
        _observability_manager = ObservabilityManager(config=config)
        await _observability_manager.initialize()
    return _observability_manager
