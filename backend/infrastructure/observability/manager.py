from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio
import time
import json
import uuid

from infrastructure.logging import get_logger
from infrastructure.metrics.collector import MetricsCollector
from infrastructure.monitoring.health import HealthChecker as MonitoringHealthChecker, FunctionHealthCheck

logger = get_logger("infrastructure.observability.manager")


class MetricType(str, Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class Metric:
    name: str
    type: MetricType
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))


@dataclass
class Span:
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
    service_name: str
    status: str
    checks: Dict[str, bool] = field(default_factory=dict)
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))
    message: str = ""


class HealthCheckerAdapter:
    def __init__(self, service_name: str):
        self.service_name = service_name
        self._checker = MonitoringHealthChecker()
        self._last_status: Optional[HealthStatus] = None

    def register_check(self, name: str, check_func: Callable):
        check = FunctionHealthCheck(name, check_func)
        self._checker.register_check(name, check)

    async def check(self) -> HealthStatus:
        results = await self._checker.check_all()

        all_healthy = all(
            r.status.value in ("OK",) for r in results.values()
        )

        checks = {
            name: r.status.value == "OK"
            for name, r in results.items()
        }

        status = HealthStatus(
            service_name=self.service_name,
            status="healthy" if all_healthy else "unhealthy",
            checks=checks,
            message="All checks passed" if all_healthy else "Some checks failed",
        )

        self._last_status = status
        return status

    async def liveness_check(self) -> bool:
        return True

    async def readiness_check(self) -> bool:
        if not self._last_status:
            return True
        return self._last_status.status == "healthy"


class Tracer:
    def __init__(self, service_name: str):
        self.service_name = service_name
        self._spans: Dict[str, Span] = {}
        self._current_trace: Optional[str] = None
        self._lock = asyncio.Lock()

    def start_trace(self) -> str:
        self._current_trace = str(uuid.uuid4()).replace("-", "")
        return self._current_trace

    def start_span(
        self,
        name: str,
        trace_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
        labels: Optional[Dict[str, str]] = None,
    ) -> Span:
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
        span.finish()

    async def get_traces(
        self,
        trace_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Span]:
        if trace_id:
            return [s for s in self._spans.values() if s.trace_id == trace_id]
        return list(self._spans.values())[-limit:]

    async def get_spans_by_service(self, service_name: str) -> List[Span]:
        return [s for s in self._spans.values() if s.service_name == service_name]


class ObservabilityManager:

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.metrics = MetricsCollector()
        self.tracer = Tracer(service_name)
        self.health_checker = HealthCheckerAdapter(service_name)

        self._start_time = int(time.time() * 1000)

    def record_request(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        duration_ms: float,
    ):
        labels = {
            "endpoint": endpoint,
            "method": method,
            "status": str(status_code),
        }

        self.metrics.increment("http_requests_total", 1, labels)
        self.metrics.observe("http_request_duration_ms", duration_ms, labels)

        if status_code >= 500:
            self.metrics.increment("http_errors_total", 1, labels)

    def record_error(self, error_type: str, message: str):
        self.metrics.increment("errors_total", 1, {"type": error_type})

    def record_business_event(self, event_name: str, labels: Optional[Dict[str, str]] = None):
        self.metrics.increment(f"business_events_{event_name}", 1, labels)

    def start_operation(self, operation_name: str, labels: Optional[Dict[str, str]] = None) -> Span:
        span = self.tracer.start_span(operation_name, labels=labels)
        return span

    def end_operation(self, span: Span, success: bool = True):
        span.add_event("operation_complete", {"success": str(success)})
        self.tracer.end_span(span)

        duration = span.duration_ms or 0
        self.metrics.observe(
            f"operation_duration_ms_{span.name}",
            duration,
            {"service": self.service_name}
        )

    async def get_status(self) -> Dict[str, Any]:
        health = await self.health_checker.check()

        uptime_ms = int(time.time() * 1000) - self._start_time

        return {
            "service": self.service_name,
            "status": health.status,
            "uptime_ms": uptime_ms,
            "health": {
                "service_name": health.service_name,
                "status": health.status,
                "checks": health.checks,
            },
        }

    def to_dict(self) -> Dict[str, Any]:
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
    if service_name not in _observability_managers:
        _observability_managers[service_name] = ObservabilityManager(service_name)
    return _observability_managers[service_name]
