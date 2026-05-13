"""
Prometheus Exporter - Prometheus 指标导出器

功能：
1. 指标暴露 (HTTP endpoint)
2. 自定义指标注册
3. 标签管理
4. 指标聚合
"""

import asyncio
import time
import threading
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from dataclasses import dataclass, field
from collections import defaultdict
import re

from infrastructure.logging import get_logger

logger = get_logger("infrastructure.observability.prometheus")

try:
    from prometheus_client import (
        Counter,
        Gauge,
        Histogram,
        Summary,
        Info,
        Enum,
        CollectorRegistry,
        generate_latest,
        CONTENT_TYPE_LATEST,
        start_http_server,
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    Counter = None
    Gauge = None
    Histogram = None
    logger.warning("prometheus_client not installed. Run: pip install prometheus-client")


@dataclass
class PrometheusConfig:
    """Prometheus 配置"""
    port: int = 9090
    prefix: str = "trade_agent"
    
    enable_default_metrics: bool = True
    enable_process_metrics: bool = True
    
    histogram_buckets: List[float] = field(default_factory=lambda: [
        0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0
    ])
    
    labels: Dict[str, str] = field(default_factory=dict)


class PrometheusExporter:
    """Prometheus 导出器
    
    提供完整的 Prometheus 指标暴露能力
    """
    
    def __init__(self, config: Optional[PrometheusConfig] = None):
        self.config = config or PrometheusConfig()
        
        self._registry: Optional[CollectorRegistry] = None
        self._metrics: Dict[str, Any] = {}
        self._initialized = False
        self._server_started = False
        
        self._counters: Dict[str, Counter] = {}
        self._gauges: Dict[str, Gauge] = {}
        self._histograms: Dict[str, Histogram] = {}
        self._summaries: Dict[str, Summary] = {}
    
    def initialize(self) -> None:
        """初始化"""
        if self._initialized:
            return
        
        if not PROMETHEUS_AVAILABLE:
            logger.warning("Prometheus client not available")
            self._initialized = True
            return
        
        self._registry = CollectorRegistry()
        
        if self.config.enable_default_metrics:
            self._register_default_metrics()
        
        self._initialized = True
        logger.info(f"PrometheusExporter initialized (prefix={self.config.prefix})")
    
    def _register_default_metrics(self) -> None:
        """注册默认指标"""
        self.create_counter(
            "events_total",
            "Total number of events processed",
            ["service", "event_type", "source"],
        )
        
        self.create_counter(
            "events_errors_total",
            "Total number of event processing errors",
            ["service", "error_type"],
        )
        
        self.create_histogram(
            "event_processing_duration_seconds",
            "Event processing duration in seconds",
            ["service", "event_type"],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
        )
        
        self.create_gauge(
            "events_in_flight",
            "Number of events currently being processed",
            ["service"],
        )
        
        self.create_counter(
            "kafka_messages_consumed_total",
            "Total number of Kafka messages consumed",
            ["topic", "partition", "consumer_group"],
        )
        
        self.create_counter(
            "kafka_messages_produced_total",
            "Total number of Kafka messages produced",
            ["topic"],
        )
        
        self.create_gauge(
            "kafka_consumer_lag",
            "Kafka consumer lag",
            ["topic", "partition", "consumer_group"],
        )
        
        self.create_histogram(
            "kafka_message_processing_duration_seconds",
            "Kafka message processing duration",
            ["topic"],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
        )
        
        self.create_counter(
            "orders_total",
            "Total number of orders",
            ["exchange", "symbol", "side", "status"],
        )
        
        self.create_gauge(
            "positions_count",
            "Number of open positions",
            ["exchange", "symbol"],
        )
        
        self.create_gauge(
            "position_pnl",
            "Position PnL",
            ["exchange", "symbol"],
        )
        
        self.create_counter(
            "trades_total",
            "Total number of trades",
            ["exchange", "symbol", "side"],
        )
        
        self.create_histogram(
            "order_execution_duration_seconds",
            "Order execution duration",
            ["exchange", "order_type"],
            buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
        )
        
        self.create_gauge(
            "risk_score",
            "Current risk score",
            ["strategy"],
        )
        
        self.create_gauge(
            "capital_available",
            "Available capital",
            [],
        )
        
        self.create_counter(
            "signals_total",
            "Total number of signals generated",
            ["strategy", "symbol", "direction"],
        )
        
        self.create_histogram(
            "strategy_decision_duration_seconds",
            "Strategy decision duration",
            ["strategy"],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0],
        )
    
    def _make_metric_name(self, name: str) -> str:
        """生成指标名称"""
        metric_name = f"{self.config.prefix}_{name}"
        metric_name = re.sub(r'[^a-zA-Z0-9_]', '_', metric_name)
        return metric_name
    
    def create_counter(
        self,
        name: str,
        description: str,
        labels: List[str],
    ) -> Optional[Counter]:
        """创建计数器"""
        if not PROMETHEUS_AVAILABLE:
            return None
        
        metric_name = self._make_metric_name(name)
        
        if metric_name in self._counters:
            return self._counters[metric_name]
        
        counter = Counter(
            metric_name,
            description,
            labels,
            registry=self._registry,
        )
        
        self._counters[metric_name] = counter
        self._metrics[metric_name] = {
            "type": "counter",
            "description": description,
            "labels": labels,
        }
        
        return counter
    
    def create_gauge(
        self,
        name: str,
        description: str,
        labels: List[str],
    ) -> Optional[Gauge]:
        """创建仪表"""
        if not PROMETHEUS_AVAILABLE:
            return None
        
        metric_name = self._make_metric_name(name)
        
        if metric_name in self._gauges:
            return self._gauges[metric_name]
        
        gauge = Gauge(
            metric_name,
            description,
            labels,
            registry=self._registry,
        )
        
        self._gauges[metric_name] = gauge
        self._metrics[metric_name] = {
            "type": "gauge",
            "description": description,
            "labels": labels,
        }
        
        return gauge
    
    def create_histogram(
        self,
        name: str,
        description: str,
        labels: List[str],
        buckets: Optional[List[float]] = None,
    ) -> Optional[Histogram]:
        """创建直方图"""
        if not PROMETHEUS_AVAILABLE:
            return None
        
        metric_name = self._make_metric_name(name)
        
        if metric_name in self._histograms:
            return self._histograms[metric_name]
        
        histogram = Histogram(
            metric_name,
            description,
            labels,
            buckets=buckets or self.config.histogram_buckets,
            registry=self._registry,
        )
        
        self._histograms[metric_name] = histogram
        self._metrics[metric_name] = {
            "type": "histogram",
            "description": description,
            "labels": labels,
        }
        
        return histogram
    
    def create_summary(
        self,
        name: str,
        description: str,
        labels: List[str],
    ) -> Optional[Summary]:
        """创建摘要"""
        if not PROMETHEUS_AVAILABLE:
            return None
        
        metric_name = self._make_metric_name(name)
        
        if metric_name in self._summaries:
            return self._summaries[metric_name]
        
        summary = Summary(
            metric_name,
            description,
            labels,
            registry=self._registry,
        )
        
        self._summaries[metric_name] = summary
        self._metrics[metric_name] = {
            "type": "summary",
            "description": description,
            "labels": labels,
        }
        
        return summary
    
    def increment_counter(
        self,
        name: str,
        value: float = 1.0,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """增加计数器"""
        metric_name = self._make_metric_name(name)
        counter = self._counters.get(metric_name)
        
        if counter is None:
            return
        
        try:
            if labels:
                counter.labels(**labels).inc(value)
            else:
                counter.inc(value)
        except Exception as e:
            logger.debug(f"Failed to increment counter {name}: {e}")
    
    def set_gauge(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """设置仪表"""
        metric_name = self._make_metric_name(name)
        gauge = self._gauges.get(metric_name)
        
        if gauge is None:
            return
        
        try:
            if labels:
                gauge.labels(**labels).set(value)
            else:
                gauge.set(value)
        except Exception as e:
            logger.debug(f"Failed to set gauge {name}: {e}")
    
    def observe_histogram(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """观察直方图"""
        metric_name = self._make_metric_name(name)
        histogram = self._histograms.get(metric_name)
        
        if histogram is None:
            return
        
        try:
            if labels:
                histogram.labels(**labels).observe(value)
            else:
                histogram.observe(value)
        except Exception as e:
            logger.debug(f"Failed to observe histogram {name}: {e}")
    
    def time_histogram(
        self,
        name: str,
        labels: Optional[Dict[str, str]] = None,
    ) -> Any:
        """计时上下文"""
        metric_name = self._make_metric_name(name)
        histogram = self._histograms.get(metric_name)
        
        if histogram is None:
            return None
        
        if labels:
            return histogram.labels(**labels).time()
        return histogram.time()
    
    def start_server(self, port: Optional[int] = None) -> None:
        """启动 HTTP 服务器"""
        if not PROMETHEUS_AVAILABLE:
            logger.warning("Cannot start Prometheus server: prometheus_client not available")
            return
        
        if self._server_started:
            return
        
        port = port or self.config.port
        
        try:
            start_http_server(port, registry=self._registry)
            self._server_started = True
            logger.info(f"Prometheus metrics server started on port {port}")
        except Exception as e:
            logger.error(f"Failed to start Prometheus server: {e}")
    
    def get_metrics(self) -> bytes:
        """获取指标数据"""
        if not PROMETHEUS_AVAILABLE:
            return b""
        
        return generate_latest(self._registry)
    
    def get_content_type(self) -> str:
        """获取内容类型"""
        if not PROMETHEUS_AVAILABLE:
            return "text/plain"
        return CONTENT_TYPE_LATEST
    
    def get_registered_metrics(self) -> Dict[str, Any]:
        """获取已注册的指标"""
        return self._metrics.copy()
    
    def clear_metrics(self) -> None:
        """清除所有指标"""
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()
        self._summaries.clear()
        self._metrics.clear()
        
        if self._registry:
            self._registry = CollectorRegistry()
        
        logger.info("All metrics cleared")


_prometheus_exporter: Optional[PrometheusExporter] = None


def get_prometheus_exporter(
    config: Optional[PrometheusConfig] = None,
) -> PrometheusExporter:
    """获取 Prometheus 导出器实例"""
    global _prometheus_exporter
    if _prometheus_exporter is None:
        _prometheus_exporter = PrometheusExporter(config)
        _prometheus_exporter.initialize()
    return _prometheus_exporter


def increment_counter(name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
    """便捷函数：增加计数器"""
    exporter = get_prometheus_exporter()
    exporter.increment_counter(name, value, labels)


def set_gauge(name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
    """便捷函数：设置仪表"""
    exporter = get_prometheus_exporter()
    exporter.set_gauge(name, value, labels)


def observe_histogram(name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
    """便捷函数：观察直方图"""
    exporter = get_prometheus_exporter()
    exporter.observe_histogram(name, value, labels)
