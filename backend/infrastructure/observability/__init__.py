"""
Observability Module - 可观测性模块

提供完整的系统监控能力：
1. 分布式追踪 (Tracing) - OpenTelemetry
2. 指标采集 (Metrics) - Prometheus
3. 事件监控 (Event Monitoring) - Lag, Loss Detection
4. 日志关联 (Log Correlation)
5. 服务注册与发现 (Service Registry)
6. 监控面板 API (Monitoring Dashboard)
"""

from .lag_monitor import (
    ConsumerLagMonitor,
    ConsumerLag,
    LagLevel,
    LagThreshold,
    get_lag_monitor,
)

from .event_loss import (
    EventLossDetector,
    EventAnomaly,
    EventQualityStats,
    DeterministicRebuilder,
    AnomalyType,
    get_event_loss_detector,
)

from .telemetry import (
    TelemetryManager,
    TelemetryConfig,
    SpanContext,
    get_telemetry_manager,
    trace_span,
)

from .prometheus import (
    PrometheusExporter,
    PrometheusConfig,
    get_prometheus_exporter,
    increment_counter,
    set_gauge,
    observe_histogram,
)

from .manager import (
    MetricType,
    Metric,
    Span,
    HealthStatus,
    MetricsCollector,
    Tracer,
    HealthChecker,
    ObservabilityManager,
    get_observability_manager,
)

from .service_registry import (
    ServiceStatus,
    ServiceEndpoint,
    ServiceInfo,
    ServiceRegistry,
    get_service_registry,
    ServiceClient,
    get_service_client,
)

from .monitoring_api import (
    DashboardMetric,
    DashboardPanel,
    MonitoringDashboard,
    create_dashboard_routes,
    get_dashboard,
)

__all__ = [
    "ConsumerLagMonitor",
    "ConsumerLag",
    "LagLevel",
    "LagThreshold",
    "get_lag_monitor",
    "EventLossDetector",
    "EventAnomaly",
    "EventQualityStats",
    "DeterministicRebuilder",
    "AnomalyType",
    "get_event_loss_detector",
    "TelemetryManager",
    "TelemetryConfig",
    "SpanContext",
    "get_telemetry_manager",
    "trace_span",
    "PrometheusExporter",
    "PrometheusConfig",
    "get_prometheus_exporter",
    "increment_counter",
    "set_gauge",
    "observe_histogram",
    "MetricType",
    "Metric",
    "Span",
    "HealthStatus",
    "MetricsCollector",
    "Tracer",
    "HealthChecker",
    "ObservabilityManager",
    "get_observability_manager",
    "ServiceStatus",
    "ServiceEndpoint",
    "ServiceInfo",
    "ServiceRegistry",
    "get_service_registry",
    "ServiceClient",
    "get_service_client",
    "DashboardMetric",
    "DashboardPanel",
    "MonitoringDashboard",
    "create_dashboard_routes",
    "get_dashboard",
]
