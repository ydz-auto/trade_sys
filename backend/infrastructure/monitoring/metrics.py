"""
指标采集模块
"""

import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from collections import defaultdict
import asyncio


@dataclass
class MetricPoint:
    name: str
    value: float
    tags: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    metric_type: str = "gauge"


@dataclass
class Counter:
    name: str
    value: float = 0
    tags: Dict[str, str] = field(default_factory=dict)

    def increment(self, value: float = 1):
        self.value += value

    def reset(self):
        self.value = 0


@dataclass
class Gauge:
    name: str
    value: float = 0
    tags: Dict[str, str] = field(default_factory=dict)

    def set(self, value: float):
        self.value = value

    def increment(self, value: float = 1):
        self.value += value

    def decrement(self, value: float = 1):
        self.value -= value


@dataclass
class Histogram:
    name: str
    values: List[float] = field(default_factory=list)
    tags: Dict[str, str] = field(default_factory=dict)

    def observe(self, value: float):
        self.values.append(value)

    def get_stats(self) -> Dict[str, float]:
        if not self.values:
            return {"count": 0, "sum": 0, "avg": 0, "min": 0, "max": 0}

        sorted_values = sorted(self.values)
        count = len(sorted_values)

        return {
            "count": count,
            "sum": sum(sorted_values),
            "avg": sum(sorted_values) / count,
            "min": sorted_values[0],
            "max": sorted_values[-1],
            "p50": sorted_values[int(count * 0.5)],
            "p90": sorted_values[int(count * 0.9)],
            "p99": sorted_values[int(count * 0.99)],
        }

    def clear(self):
        self.values.clear()


class MetricsCollector:
    def __init__(self):
        self._counters: Dict[str, Counter] = {}
        self._gauges: Dict[str, Gauge] = {}
        self._histograms: Dict[str, Histogram] = {}
        self._metrics_history: List[MetricPoint] = []
        self._max_history_size = 10000
        self._exporters: List[Callable] = []

    def register_exporter(self, exporter: Callable):
        self._exporters.append(exporter)

    def _make_key(self, name: str, tags: Dict[str, str]) -> str:
        tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name}:{tag_str}"

    def counter(self, name: str, tags: Optional[Dict[str, str]] = None) -> Counter:
        tags = tags or {}
        key = self._make_key(name, tags)
        if key not in self._counters:
            self._counters[key] = Counter(name=name, tags=tags)
        return self._counters[key]

    def gauge(self, name: str, tags: Optional[Dict[str, str]] = None) -> Gauge:
        tags = tags or {}
        key = self._make_key(name, tags)
        if key not in self._gauges:
            self._gauges[key] = Gauge(name=name, tags=tags)
        return self._gauges[key]

    def histogram(self, name: str, tags: Optional[Dict[str, str]] = None) -> Histogram:
        tags = tags or {}
        key = self._make_key(name, tags)
        if key not in self._histograms:
            self._histograms[key] = Histogram(name=name, tags=tags)
        return self._histograms[key]

    def increment(
        self,
        name: str,
        value: float = 1,
        tags: Optional[Dict[str, str]] = None,
    ):
        c = self.counter(name, tags)
        c.increment(value)
        self._record_metric(name, c.value, tags, "counter")

    def set_gauge(
        self,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None,
    ):
        g = self.gauge(name, tags)
        g.set(value)
        self._record_metric(name, value, tags, "gauge")

    def observe(
        self,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None,
    ):
        h = self.histogram(name, tags)
        h.observe(value)
        self._record_metric(name, value, tags, "histogram")

    def _record_metric(
        self,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]],
        metric_type: str,
    ):
        point = MetricPoint(
            name=name,
            value=value,
            tags=tags or {},
            timestamp=time.time(),
            metric_type=metric_type,
        )
        self._metrics_history.append(point)

        if len(self._metrics_history) > self._max_history_size:
            self._metrics_history = self._metrics_history[-self._max_history_size :]

        for exporter in self._exporters:
            try:
                exporter(point)
            except Exception:
                pass

    def get_counter(self, name: str, tags: Optional[Dict[str, str]] = None) -> float:
        tags = tags or {}
        key = self._make_key(name, tags)
        return self._counters.get(key, Counter(name=name, tags=tags)).value

    def get_gauge(self, name: str, tags: Optional[Dict[str, str]] = None) -> float:
        tags = tags or {}
        key = self._make_key(name, tags)
        return self._gauges.get(key, Gauge(name=name, tags=tags)).value

    def get_histogram_stats(
        self,
        name: str,
        tags: Optional[Dict[str, str]] = None,
    ) -> Dict[str, float]:
        tags = tags or {}
        key = self._make_key(name, tags)
        return self._histograms.get(key, Histogram(name=name, tags=tags)).get_stats()

    def get_all_metrics(self) -> Dict[str, Any]:
        result = {
            "counters": {},
            "gauges": {},
            "histograms": {},
            "timestamp": time.time(),
        }

        for key, counter in self._counters.items():
            result["counters"][key] = {"value": counter.value, "tags": counter.tags}

        for key, gauge in self._gauges.items():
            result["gauges"][key] = {"value": gauge.value, "tags": gauge.tags}

        for key, histogram in self._histograms.items():
            result["histograms"][key] = {
                "stats": histogram.get_stats(),
                "tags": histogram.tags,
            }

        return result

    def reset(self):
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()
        self._metrics_history.clear()


class PrometheusExporter:
    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics = metrics_collector
        self._lines: List[str] = []

    def export(self, point: MetricPoint):
        self._lines.append(self._format_point(point))

    def _format_point(self, point: MetricPoint) -> str:
        tags_str = ""
        if point.tags:
            tags_str = ",".join(f'{k}="{v}"' for k, v in point.tags.items())
            tags_str = f"{{{tags_str}}}"

        metric_name = point.name.replace("-", "_").replace(".", "_")
        return f"{metric_name}{tags_str} {point.value} {int(point.timestamp * 1000)}"

    def get_prometheus_format(self) -> str:
        self._lines.clear()
        for key, counter in self.metrics._counters.items():
            metric_name = counter.name.replace("-", "_").replace(".", "_")
            tags_str = ""
            if counter.tags:
                tags_str = ",".join(f'{k}="{v}"' for k, v in counter.tags.items())
                tags_str = f"{{{tags_str}}}"
            self._lines.append(f"{metric_name}{tags_str} {counter.value}")

        for key, gauge in self.metrics._gauges.items():
            metric_name = gauge.name.replace("-", "_").replace(".", "_")
            tags_str = ""
            if gauge.tags:
                tags_str = ",".join(f'{k}="{v}"' for k, v in gauge.tags.items())
                tags_str = f"{{{tags_str}}}"
            self._lines.append(f"{metric_name}{tags_str} {gauge.value}")

        return "\n".join(self._lines)


metrics_collector = MetricsCollector()


def record_latency(service: str, operation: str, latency_ms: float):
    metrics_collector.observe(
        f"{service}.latency",
        latency_ms,
        tags={"operation": operation},
    )


def record_error(service: str, error_type: str):
    metrics_collector.increment(
        f"{service}.errors",
        tags={"error_type": error_type},
    )


def record_request(service: str, endpoint: str, status_code: int):
    metrics_collector.increment(
        f"{service}.requests",
        tags={"endpoint": endpoint, "status": str(status_code)},
    )