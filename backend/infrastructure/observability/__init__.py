"""
Observability Module - 可观测性模块

提供完整的系统监控能力：
1. 分布式追踪 (Tracing) - OpenTelemetry
2. 指标采集 (Metrics) - Prometheus
3. 事件监控 (Event Monitoring) - Lag, Loss Detection
4. 日志关联 (Log Correlation)
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
]
