"""
Observability Module - 可观测性模块
提供指标、追踪和健康检查功能
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio
import time
import json
import uuid

from infrastructure.logging import get_logger

logger = get_logger("infrastructure.observability.manager")


class MetricType(str, Enum):
    """指标类型"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class Metric:
    """指标"""
    name: str
    type: MetricType
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))


@dataclass
class Span:
    """追踪跨度"""
    span_id: str
    trace_id: str
    name: str
    service_name: str

    start_time: int
    end_time: Optional[int] = None

    labels: Dict[str, str] = field(default_factory=dict)
    events: List[Dict] = field(default_factory=list)

    parent_span_id: Optional[str] = None

    def add_event(self, name: str, labels: Optional[Dict[str, str]] = None):
        self.events.append({
            "name": name,
            "timestamp": int(time.time() * 1000),
            "labels": labels or {},
        })

    def finish(self):
        self.end_time = int(time.time() * 1000)

    @property
    def duration_ms(self) -> Optional[float]:
        if self.end_time:
            return (self.end_time - self.start_time) / 1000.0
        return None


@dataclass
class HealthStatus:
    """健康状态"""
    service_name: str
    status: str
    checks: Dict[str, bool] = field(default_factory=dict)
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))
    message: str = ""


class MetricsCollector:
    """指标收集器"""

    def __init__(self):
        self._metrics: Dict[str, float] = {}
        self._counters: Dict[str, float] = {}
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = {}
        self._labels: Dict[str, Dict[str, str]] = {}

        self._lock = asyncio.Lock()

    def counter(self, name: str, value: float = 1, labels: Optional[Dict[str, str]] = None):
        """增加计数器"""
        key = self._make_key(name, labels)
        self._counters[key] = self._counters.get(key, 0) + value

    def gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """设置仪表值"""
        key = self._make_key(name, labels)
        self._gauges[key] = value
        self._labels[key] = labels or {}

    def histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """记录直方图值"""
        key = self._make_key(name, labels)
        if key not in self._histograms:
            self._histograms[key] = []
        self._histograms[key].append(value)
        self._labels[key] = labels or {}

    def summary(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """记录汇总值"""
        self.histogram(name, value, labels)

    def _make_key(self, name: str, labels: Optional[Dict[str, str]]) -> str:
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    async def get_metrics(self) -> List[Metric]:
        """获取所有指标"""
        metrics = []

        for key, value in self._counters.items():
            metrics.append(Metric(
                name=key.split("{")[0],
                type=MetricType.COUNTER,
                value=value,
                labels=self._labels.get(key, {}),
            ))

        for key, value in self._gauges.items():
            metrics.append(Metric(
                name=key.split("{")[0],
                type=MetricType.GAUGE,
                value=value,
                labels=self._labels.get(key, {}),
            ))

        for key, values in self._histograms.items():
            if values:
                avg = sum(values) / len(values)
                metrics.append(Metric(
                    name=key.split("{")[0],
                    type=MetricType.HISTOGRAM,
                    value=avg,
                    labels=self._labels.get(key, {}),
                ))

        return metrics

    async def get_prometheus_format(self) -> str:
        """获取 Prometheus 格式"""
        lines = []

        for key, value in self._counters.items():
            name = key.split("{")[0]
            labels_str = key[len(name):]
            lines.append(f"{name}_total{labels_str} {value}")

        for key, value in self._gauges.items():
            name = key.split("{")[0]
            labels_str = key[len(name):]
            lines.append(f"{name}{labels_str} {value}")

        for key, values in self._histograms.items():
            if values:
                name = key.split("{")[0]
                labels_str = key[len(name):]
                avg = sum(values) / len(values)
                lines.append(f"{name}_sum{labels_str} {avg}")
                lines.append(f"{name}_count{labels_str} {len(values)}")

        return "\n".join(lines)

    def reset(self):
        """重置所有指标"""
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()


class Tracer:
    """追踪器"""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self._spans: Dict[str, Span] = {}
        self._current_trace: Optional[str] = None
        self._lock = asyncio.Lock()

    def start_trace(self) -> str:
        """开始新的追踪"""
        self._current_trace = str(uuid.uuid4()).replace("-", "")
        return self._current_trace

    def start_span(
        self,
        name: str,
        trace_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
        labels: Optional[Dict[str, str]] = None,
    ) -> Span:
        """开始新的跨度"""
        span_id = str(uuid.uuid4()).replace("-", "")[:16]
        trace = trace_id or self._current_trace or self.start_trace()

        span = Span(
            span_id=span_id,
            trace_id=trace,
            name=name,
            service_name=self.service_name,
            start_time=int(time.time() * 1000),
            labels=labels or {},
            parent_span_id=parent_span_id,
        )

        self._spans[span_id] = span
        return span

    def end_span(self, span: Span):
        """结束跨度"""
        span.finish()

    async def get_traces(
        self,
        trace_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Span]:
        """获取追踪"""
        if trace_id:
            return [s for s in self._spans.values() if s.trace_id == trace_id]
        return list(self._spans.values())[-limit:]

    async def get_spans_by_service(self, service_name: str) -> List[Span]:
        """获取服务跨度"""
        return [s for s in self._spans.values() if s.service_name == service_name]


class HealthChecker:
    """健康检查器"""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self._checks: Dict[str, Callable] = {}
        self._last_status: Optional[HealthStatus] = None

    def register_check(self, name: str, check_func: Callable):
        """注册健康检查"""
        self._checks[name] = check_func

    async def check(self) -> HealthStatus:
        """执行健康检查"""
        results = {}
        all_healthy = True

        for name, check_func in self._checks.items():
            try:
                if asyncio.iscoroutinefunction(check_func):
                    result = await check_func()
                else:
                    result = check_func()

                results[name] = bool(result)
                if not result:
                    all_healthy = False
            except Exception as e:
                logger.error(f"Health check failed for {name}: {e}")
                results[name] = False
                all_healthy = False

        status = HealthStatus(
            service_name=self.service_name,
            status="healthy" if all_healthy else "unhealthy",
            checks=results,
            message="All checks passed" if all_healthy else "Some checks failed",
        )

        self._last_status = status
        return status

    async def liveness_check(self) -> bool:
        """存活检查"""
        return True

    async def readiness_check(self) -> bool:
        """就绪检查"""
        if not self._last_status:
            return True
        return self._last_status.status == "healthy"


class ObservabilityManager:
    """可观测性管理器"""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.metrics = MetricsCollector()
        self.tracer = Tracer(service_name)
        self.health_checker = HealthChecker(service_name)

        self._start_time = int(time.time() * 1000)

    def record_request(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        duration_ms: float,
    ):
        """记录请求"""
        labels = {
            "endpoint": endpoint,
            "method": method,
            "status": str(status_code),
        }

        self.metrics.counter("http_requests_total", 1, labels)
        self.metrics.histogram("http_request_duration_ms", duration_ms, labels)

        if status_code >= 500:
            self.metrics.counter("http_errors_total", 1, labels)

    def record_error(self, error_type: str, message: str):
        """记录错误"""
        self.metrics.counter("errors_total", 1, {"type": error_type})

    def record_business_event(self, event_name: str, labels: Optional[Dict[str, str]] = None):
        """记录业务事件"""
        self.metrics.counter(f"business_events_{event_name}", 1, labels)

    def start_operation(self, operation_name: str, labels: Optional[Dict[str, str]] = None) -> Span:
        """开始操作追踪"""
        span = self.tracer.start_span(operation_name, labels=labels)
        return span

    def end_operation(self, span: Span, success: bool = True):
        """结束操作追踪"""
        span.add_event("operation_complete", {"success": str(success)})
        self.tracer.end_span(span)

        duration = span.duration_ms or 0
        self.metrics.histogram(
            f"operation_duration_ms_{span.name}",
            duration,
            {"service": self.service_name}
        )

    async def get_status(self) -> Dict[str, Any]:
        """获取整体状态"""
        health = await self.health_checker.check()

        uptime_ms = int(time.time() * 1000) - self._start_time

        return {
            "service": self.service_name,
            "status": health.status,
            "uptime_ms": uptime_ms,
            "health": health.to_dict() if hasattr(health, 'to_dict') else {
                "service_name": health.service_name,
                "status": health.status,
                "checks": health.checks,
            },
        }

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "service_name": self.service_name,
            "metrics": {
                "counters": self.metrics._counters,
                "gauges": self.metrics._gauges,
                "histograms": {k: len(v) for k, v in self.metrics._histograms.items()},
            },
        }


_observability_managers: Dict[str, ObservabilityManager] = {}


def get_observability_manager(service_name: str) -> ObservabilityManager:
    """获取可观测性管理器"""
    if service_name not in _observability_managers:
        _observability_managers[service_name] = ObservabilityManager(service_name)
    return _observability_managers[service_name]
