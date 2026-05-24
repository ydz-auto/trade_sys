import asyncio
import time
from typing import Dict, List, Optional, Any

from infrastructure.logging import get_logger
from infrastructure.metrics.collector import metrics_collector, MetricsCollector

try:
    from prometheus_client import (
        Counter,
        Gauge,
        Histogram,
        CollectorRegistry,
        generate_latest,
        start_http_server,
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    Counter = None
    Gauge = None
    Histogram = None
    CollectorRegistry = None
    generate_latest = None
    start_http_server = None

logger = get_logger("infrastructure.metrics.prometheus_server")


class PrometheusMetricsServer:

    def __init__(self, port: int = 9090, metrics_collector: Optional[MetricsCollector] = None):
        if not PROMETHEUS_AVAILABLE:
            raise RuntimeError("prometheus_client not installed. Run: pip install prometheus-client")

        self.port = port
        self.metrics_collector = metrics_collector or metrics_collector
        self._registry = CollectorRegistry()
        self._custom_metrics: Dict[str, Any] = {}
        self._server = None
        self._running = False
        self._start_time = time.time()

    async def initialize(self) -> None:
        self.register_trading_metrics()
        self.register_system_metrics()
        self.register_pipeline_metrics()
        logger.info(f"Prometheus metrics server initialized on port {self.port}")

    async def start(self) -> None:
        if self._running:
            return

        try:
            start_http_server(self.port, registry=self._registry)
            self._running = True
            logger.info(f"Prometheus metrics server started on port {self.port}")
        except OSError as e:
            logger.error(f"Failed to start Prometheus server on port {self.port}: {e}")
            raise

    async def stop(self) -> None:
        self._running = False
        self._custom_metrics.clear()
        logger.info("Prometheus metrics server stopped")

    def register_counter(self, name: str, description: str, labels: Optional[List[str]] = None) -> None:
        if name in self._custom_metrics:
            logger.warning(f"Metric {name} already registered, skipping")
            return

        if labels:
            metric = Counter(name, description, labels, registry=self._registry)
        else:
            metric = Counter(name, description, registry=self._registry)
        self._custom_metrics[name] = metric

    def register_gauge(self, name: str, description: str, labels: Optional[List[str]] = None) -> None:
        if name in self._custom_metrics:
            logger.warning(f"Metric {name} already registered, skipping")
            return

        if labels:
            metric = Gauge(name, description, labels, registry=self._registry)
        else:
            metric = Gauge(name, description, registry=self._registry)
        self._custom_metrics[name] = metric

    def register_histogram(
        self,
        name: str,
        description: str,
        buckets: Optional[List[float]] = None,
        labels: Optional[List[str]] = None,
    ) -> None:
        if name in self._custom_metrics:
            logger.warning(f"Metric {name} already registered, skipping")
            return

        kwargs: Dict[str, Any] = {}
        if buckets:
            kwargs["buckets"] = buckets
        if labels:
            kwargs["labelnames"] = labels

        metric = Histogram(name, description, registry=self._registry, **kwargs)
        self._custom_metrics[name] = metric

    def increment_counter(self, name: str, value: float = 1, labels: Optional[Dict[str, str]] = None) -> None:
        if name not in self._custom_metrics:
            logger.warning(f"Counter {name} not registered")
            return

        metric = self._custom_metrics[name]
        if labels:
            metric.labels(**labels).inc(value)
        else:
            metric.inc(value)

    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        if name not in self._custom_metrics:
            logger.warning(f"Gauge {name} not registered")
            return

        metric = self._custom_metrics[name]
        if labels:
            metric.labels(**labels).set(value)
        else:
            metric.set(value)

    def observe_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        if name not in self._custom_metrics:
            logger.warning(f"Histogram {name} not registered")
            return

        metric = self._custom_metrics[name]
        if labels:
            metric.labels(**labels).observe(value)
        else:
            metric.observe(value)

    def register_trading_metrics(self) -> None:
        self.register_counter(
            "tradeagent_trading_orders_total",
            "Total number of trading orders",
            ["side", "symbol", "status"],
        )
        self.register_counter(
            "tradeagent_trading_fills_total",
            "Total number of order fills",
            ["side", "symbol"],
        )
        self.register_histogram(
            "tradeagent_trading_order_latency_ms",
            "Order execution latency in milliseconds",
            buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000, 5000],
            labels=["side", "symbol"],
        )
        self.register_gauge(
            "tradeagent_trading_position_size",
            "Current position size",
            ["symbol", "side"],
        )
        self.register_gauge(
            "tradeagent_trading_pnl",
            "Current PnL",
            ["symbol"],
        )
        self.register_counter(
            "tradeagent_trading_rejections_total",
            "Total number of rejected orders",
            ["reason", "symbol"],
        )

    def register_system_metrics(self) -> None:
        self.register_gauge(
            "tradeagent_system_uptime_seconds",
            "System uptime in seconds",
        )
        self.register_gauge(
            "tradeagent_system_info",
            "System information",
            ["version", "python_version"],
        )
        self.register_counter(
            "tradeagent_system_errors_total",
            "Total number of system errors",
            ["type", "module"],
        )
        self.register_gauge(
            "tradeagent_system_active_tasks",
            "Number of active asyncio tasks",
        )
        self.register_histogram(
            "tradeagent_system_event_processing_ms",
            "Event processing latency in milliseconds",
            buckets=[0.1, 0.5, 1, 5, 10, 50, 100, 500],
            labels=["event_type"],
        )

    def register_pipeline_metrics(self) -> None:
        self.register_counter(
            "tradeagent_pipeline_events_total",
            "Total events processed by pipeline",
            ["stage", "event_type", "status"],
        )
        self.register_histogram(
            "tradeagent_pipeline_stage_latency_ms",
            "Pipeline stage latency in milliseconds",
            buckets=[0.1, 0.5, 1, 5, 10, 50, 100, 500, 1000],
            labels=["stage"],
        )
        self.register_gauge(
            "tradeagent_pipeline_consumer_lag",
            "Consumer group lag",
            ["group_id", "topic", "partition"],
        )
        self.register_counter(
            "tradeagent_pipeline_event_loss_total",
            "Total events lost",
            ["topic", "partition", "anomaly_type"],
        )
        self.register_gauge(
            "tradeagent_pipeline_backlog_size",
            "Pipeline backlog size",
            ["stage"],
        )

    async def get_metrics_text(self) -> str:
        self.set_gauge("tradeagent_system_uptime_seconds", time.time() - self._start_time)

        try:
            active_tasks = len(asyncio.all_tasks())
            self.set_gauge("tradeagent_system_active_tasks", active_tasks)
        except RuntimeError:
            pass

        return generate_latest(self._registry).decode("utf-8")

    @property
    def is_running(self) -> bool:
        return self._running

    def get_registered_metrics(self) -> List[str]:
        return list(self._custom_metrics.keys())


_prometheus_server: Optional[PrometheusMetricsServer] = None


async def get_prometheus_server(port: int = 9090) -> PrometheusMetricsServer:
    global _prometheus_server
    if _prometheus_server is None:
        _prometheus_server = PrometheusMetricsServer(port=port)
        await _prometheus_server.initialize()
    return _prometheus_server
