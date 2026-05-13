"""
OpenTelemetry Integration - OpenTelemetry 集成

功能：
1. 分布式追踪 (Tracing)
2. 指标采集 (Metrics)
3. 日志关联 (Logs)
4. 上下文传播 (Context Propagation)

支持导出到：
- Prometheus (指标)
- Tempo/Jaeger (追踪)
- Grafana (可视化)
"""

import asyncio
import time
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from dataclasses import dataclass, field
from contextlib import contextmanager, asynccontextmanager
import functools

from infrastructure.logging import get_logger

logger = get_logger("infrastructure.observability.telemetry")

try:
    from opentelemetry import trace
    from opentelemetry import metrics
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
    from opentelemetry.context import Context
    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False
    trace = None
    metrics = None
    TracerProvider = None
    MeterProvider = None
    logger.warning("OpenTelemetry not installed. Run: pip install opentelemetry-api opentelemetry-sdk")


@dataclass
class TelemetryConfig:
    """遥测配置"""
    service_name: str = "trade-agent"
    service_version: str = "1.0.0"
    environment: str = "development"
    
    enable_tracing: bool = True
    enable_metrics: bool = True
    
    trace_sample_rate: float = 1.0
    metric_export_interval: int = 30
    
    otlp_endpoint: Optional[str] = None
    prometheus_port: int = 9090
    jaeger_host: str = "localhost"
    jaeger_port: int = 6831
    
    def get_resource_attributes(self) -> Dict[str, str]:
        return {
            "service.name": self.service_name,
            "service.version": self.service_version,
            "deployment.environment": self.environment,
        }


@dataclass
class SpanContext:
    """Span 上下文"""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    operation_name: str
    start_time: float
    
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "operation_name": self.operation_name,
            "start_time": self.start_time,
            "attributes": self.attributes,
            "events": self.events,
        }


class TelemetryManager:
    """遥测管理器
    
    统一管理 Tracing 和 Metrics
    """
    
    def __init__(self, config: Optional[TelemetryConfig] = None):
        self.config = config or TelemetryConfig()
        
        self._tracer = None
        self._meter = None
        self._tracer_provider = None
        self._meter_provider = None
        
        self._propagator = None
        self._initialized = False
        
        self._metrics_registry: Dict[str, Any] = {}
        self._active_spans: Dict[str, SpanContext] = {}
    
    def initialize(self) -> None:
        """初始化"""
        if self._initialized:
            return
        
        if not OPENTELEMETRY_AVAILABLE:
            logger.warning("OpenTelemetry not available, using no-op implementation")
            self._initialized = True
            return
        
        try:
            if self.config.enable_tracing:
                self._setup_tracing()
            
            if self.config.enable_metrics:
                self._setup_metrics()
            
            self._propagator = TraceContextTextMapPropagator()
            
            self._initialized = True
            logger.info(f"TelemetryManager initialized (tracing={self.config.enable_tracing}, metrics={self.config.enable_metrics})")
            
        except Exception as e:
            logger.error(f"Failed to initialize telemetry: {e}")
            self._initialized = True
    
    def _setup_tracing(self) -> None:
        """设置追踪"""
        from opentelemetry.sdk.resources import Resource
        
        resource = Resource.create(self.config.get_resource_attributes())
        
        self._tracer_provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(self._tracer_provider)
        
        self._tracer = trace.get_tracer(
            self.config.service_name,
            self.config.service_version,
        )
        
        self._setup_trace_exporters()
    
    def _setup_trace_exporters(self) -> None:
        """设置追踪导出器"""
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            
            if self.config.otlp_endpoint:
                otlp_exporter = OTLPSpanExporter(endpoint=self.config.otlp_endpoint)
                self._tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
                logger.info(f"OTLP trace exporter configured: {self.config.otlp_endpoint}")
        except ImportError:
            pass
        
        try:
            from opentelemetry.exporter.jaeger.thrift import JaegerExporter
            
            jaeger_exporter = JaegerExporter(
                agent_host_name=self.config.jaeger_host,
                agent_port=self.config.jaeger_port,
            )
            self._tracer_provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))
            logger.info(f"Jaeger exporter configured: {self.config.jaeger_host}:{self.config.jaeger_port}")
        except ImportError:
            pass
    
    def _setup_metrics(self) -> None:
        """设置指标"""
        from opentelemetry.sdk.resources import Resource
        
        resource = Resource.create(self.config.get_resource_attributes())
        
        readers = []
        
        try:
            from opentelemetry.exporter.prometheus import PrometheusMetricReader
            
            prometheus_reader = PrometheusMetricReader()
            readers.append(prometheus_reader)
            logger.info(f"Prometheus metrics exporter configured on port {self.config.prometheus_port}")
        except ImportError:
            pass
        
        self._meter_provider = MeterProvider(
            resource=resource,
            metric_readers=readers,
        )
        metrics.set_meter_provider(self._meter_provider)
        
        self._meter = metrics.get_meter(
            self.config.service_name,
            self.config.service_version,
        )
    
    @contextmanager
    def start_span(
        self,
        operation_name: str,
        attributes: Optional[Dict[str, Any]] = None,
        parent_context: Optional[Context] = None,
    ):
        """开始一个 Span"""
        if not self._initialized:
            self.initialize()
        
        if self._tracer is None:
            yield None
            return
        
        with self._tracer.start_as_current_span(
            operation_name,
            context=parent_context,
        ) as span:
            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, value)
            
            span_context = SpanContext(
                trace_id=format(span.context.trace_id, '032x'),
                span_id=format(span.context.span_id, '016x'),
                parent_span_id=format(span.parent.span_id, '016x') if span.parent else None,
                operation_name=operation_name,
                start_time=time.time(),
                attributes=attributes or {},
            )
            
            self._active_spans[span_context.span_id] = span_context
            
            try:
                yield span
            finally:
                self._active_spans.pop(span_context.span_id, None)
    
    @asynccontextmanager
    async def start_async_span(
        self,
        operation_name: str,
        attributes: Optional[Dict[str, Any]] = None,
    ):
        """开始一个异步 Span"""
        if not self._initialized:
            self.initialize()
        
        if self._tracer is None:
            yield None
            return
        
        with self._tracer.start_as_current_span(operation_name) as span:
            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, value)
            
            try:
                yield span
            except Exception as e:
                if span:
                    span.record_exception(e)
                raise
    
    def trace_function(
        self,
        operation_name: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ):
        """函数追踪装饰器"""
        def decorator(func: Callable) -> Callable:
            name = operation_name or f"{func.__module__}.{func.__name__}"
            
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                with self.start_span(name, attributes):
                    return func(*args, **kwargs)
            
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                async with self.start_async_span(name, attributes):
                    return await func(*args, **kwargs)
            
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            return sync_wrapper
        
        return decorator
    
    def create_counter(
        self,
        name: str,
        description: str = "",
        unit: str = "1",
    ):
        """创建计数器"""
        if self._meter is None:
            return None
        
        counter = self._meter.create_counter(name, description, unit)
        self._metrics_registry[name] = counter
        return counter
    
    def create_histogram(
        self,
        name: str,
        description: str = "",
        unit: str = "ms",
    ):
        """创建直方图"""
        if self._meter is None:
            return None
        
        histogram = self._meter.create_histogram(name, description, unit)
        self._metrics_registry[name] = histogram
        return histogram
    
    def create_gauge(
        self,
        name: str,
        description: str = "",
        unit: str = "1",
    ):
        """创建可观测仪表"""
        if self._meter is None:
            return None
        
        gauge = self._meter.create_gauge(name, description, unit)
        self._metrics_registry[name] = gauge
        return gauge
    
    def record_metric(
        self,
        name: str,
        value: float,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        """记录指标"""
        metric = self._metrics_registry.get(name)
        if metric is None:
            return
        
        try:
            if hasattr(metric, 'record'):
                metric.record(value, attributes=attributes)
            elif hasattr(metric, 'add'):
                metric.add(value, attributes=attributes)
        except Exception as e:
            logger.debug(f"Failed to record metric {name}: {e}")
    
    def inject_context(self, carrier: Dict[str, str]) -> None:
        """注入上下文到载体"""
        if self._propagator:
            self._propagator.inject(carrier)
    
    def extract_context(self, carrier: Dict[str, str]) -> Context:
        """从载体提取上下文"""
        if self._propagator:
            return self._propagator.extract(carrier)
        return None
    
    def get_trace_id(self) -> Optional[str]:
        """获取当前 trace_id"""
        if not OPENTELEMETRY_AVAILABLE:
            return None
        
        span = trace.get_current_span()
        if span and span.context:
            return format(span.context.trace_id, '032x')
        return None
    
    def get_span_id(self) -> Optional[str]:
        """获取当前 span_id"""
        if not OPENTELEMETRY_AVAILABLE:
            return None
        
        span = trace.get_current_span()
        if span and span.context:
            return format(span.context.span_id, '016x')
        return None
    
    def get_active_spans(self) -> List[SpanContext]:
        """获取活跃的 Span"""
        return list(self._active_spans.values())
    
    def shutdown(self) -> None:
        """关闭"""
        if self._tracer_provider:
            self._tracer_provider.shutdown()
        
        if self._meter_provider:
            self._meter_provider.shutdown()
        
        logger.info("TelemetryManager shutdown")


_telemetry_manager: Optional[TelemetryManager] = None


def get_telemetry_manager(
    config: Optional[TelemetryConfig] = None,
) -> TelemetryManager:
    """获取遥测管理器实例"""
    global _telemetry_manager
    if _telemetry_manager is None:
        _telemetry_manager = TelemetryManager(config)
        _telemetry_manager.initialize()
    return _telemetry_manager


def trace_span(
    operation_name: str,
    attributes: Optional[Dict[str, Any]] = None,
):
    """便捷的追踪装饰器"""
    manager = get_telemetry_manager()
    return manager.trace_function(operation_name, attributes)
