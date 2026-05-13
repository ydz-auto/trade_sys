"""
Tracing Manager - OpenTelemetry 分布式追踪管理器

提供：
1. OpenTelemetry SDK 集成
2. 自动 span 创建
3. trace_id 传播
4. 与现有 BaseEvent.trace_id 集成
5. Tempo/Jaeger exporter
"""

import time
import functools
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field

from infrastructure.logging import get_logger

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.resources import Resource
    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False
    trace = None
    TracerProvider = None
    BatchSpanProcessor = None
    Resource = None

try:
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    OTLP_EXPORTER_AVAILABLE = True
except ImportError:
    OTLP_EXPORTER_AVAILABLE = False
    OTLPSpanExporter = None

logger = get_logger("infrastructure.observability.tracing")


@dataclass
class SpanContext:
    """Span 上下文"""
    span_id: str
    trace_id: str
    name: str
    start_time: float
    attributes: Dict[str, Any] = field(default_factory=dict)
    parent_span_id: Optional[str] = None
    _otel_span: Any = None

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value
        if self._otel_span is not None:
            try:
                self._otel_span.set_attribute(key, value)
            except Exception:
                pass

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        if self._otel_span is not None:
            try:
                self._otel_span.add_event(name, attributes=attributes or {})
            except Exception:
                pass

    def record_error(self, exception: Exception) -> None:
        if self._otel_span is not None:
            try:
                self._otel_span.record_exception(exception)
                self._otel_span.set_status(trace.StatusCode.ERROR, str(exception))
            except Exception:
                pass

    def end(self) -> None:
        if self._otel_span is not None:
            try:
                self._otel_span.end()
            except Exception:
                pass


class TracingManager:
    """分布式追踪管理器
    
    提供：
    1. OpenTelemetry SDK 集成
    2. 自动 span 创建
    3. trace_id 传播
    4. 与现有 BaseEvent.trace_id 集成
    5. Tempo/Jaeger exporter
    """

    def __init__(self, service_name: str = "tradeagent", otlp_endpoint: str = "localhost:4317"):
        self.service_name = service_name
        self.otlp_endpoint = otlp_endpoint
        self._tracer = None
        self._provider = None
        self._initialized = False
        self._active_spans: Dict[str, SpanContext] = {}

    async def initialize(self) -> None:
        if not OPENTELEMETRY_AVAILABLE:
            logger.warning("OpenTelemetry SDK not installed, tracing disabled")
            return

        try:
            resource = Resource.create({"service.name": self.service_name})
            self._provider = TracerProvider(resource=resource)

            if OTLP_EXPORTER_AVAILABLE:
                exporter = OTLPSpanExporter(endpoint=self.otlp_endpoint, insecure=True)
                processor = BatchSpanProcessor(exporter)
                self._provider.add_span_processor(processor)
                logger.info(f"OTLP exporter configured: {self.otlp_endpoint}")
            else:
                logger.warning("OTLP exporter not installed, traces will not be exported")

            trace.set_tracer_provider(self._provider)
            self._tracer = trace.get_tracer(self.service_name)
            self._initialized = True
            logger.info(f"Tracing manager initialized: {self.service_name}")
        except Exception as e:
            logger.error(f"Failed to initialize tracing: {e}")
            self._initialized = False

    async def shutdown(self) -> None:
        if self._provider is not None:
            try:
                self._provider.shutdown()
            except Exception as e:
                logger.error(f"Error shutting down tracer provider: {e}")

        self._active_spans.clear()
        self._initialized = False
        logger.info("Tracing manager shut down")

    def get_tracer(self, name: Optional[str] = None) -> Any:
        if not self._initialized or self._tracer is None:
            return None
        if name:
            return trace.get_tracer(name)
        return self._tracer

    def start_span(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
        parent_trace_id: Optional[str] = None,
    ) -> SpanContext:
        if not self._initialized or self._tracer is None:
            return SpanContext(
                span_id="noop",
                trace_id="noop",
                name=name,
                start_time=time.time(),
                attributes=attributes or {},
                parent_span_id=parent_trace_id,
            )

        try:
            otel_span = self._tracer.start_span(name, attributes=attributes or {})

            span_context = otel_span.get_span_context()
            span_id = format(span_context.span_id, "016x")
            trace_id = format(span_context.trace_id, "032x")

            span = SpanContext(
                span_id=span_id,
                trace_id=trace_id,
                name=name,
                start_time=time.time(),
                attributes=attributes or {},
                parent_span_id=parent_trace_id,
                _otel_span=otel_span,
            )

            self._active_spans[span_id] = span
            return span
        except Exception as e:
            logger.error(f"Failed to start span: {e}")
            return SpanContext(
                span_id="error",
                trace_id="error",
                name=name,
                start_time=time.time(),
                attributes=attributes or {},
                parent_span_id=parent_trace_id,
            )

    def end_span(self, span: SpanContext) -> None:
        if span._otel_span is not None:
            try:
                span._otel_span.end()
            except Exception as e:
                logger.error(f"Failed to end span: {e}")

        self._active_spans.pop(span.span_id, None)

    def add_span_event(self, span: SpanContext, name: str, attributes: Optional[Dict] = None) -> None:
        span.add_event(name, attributes)

    def set_span_attribute(self, span: SpanContext, key: str, value: Any) -> None:
        span.set_attribute(key, value)

    def record_span_error(self, span: SpanContext, exception: Exception) -> None:
        span.record_error(exception)

    def trace_function(self, name: Optional[str] = None) -> Callable:
        def decorator(func: Callable) -> Callable:
            span_name = name or f"{func.__module__}.{func.__qualname__}"

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                span = self.start_span(span_name)
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    self.record_span_error(span, e)
                    raise
                finally:
                    self.end_span(span)

            return wrapper
        return decorator

    def trace_async_function(self, name: Optional[str] = None) -> Callable:
        def decorator(func: Callable) -> Callable:
            span_name = name or f"{func.__module__}.{func.__qualname__}"

            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                span = self.start_span(span_name)
                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as e:
                    self.record_span_error(span, e)
                    raise
                finally:
                    self.end_span(span)

            return wrapper
        return decorator

    def create_event_span(self, event: Any) -> SpanContext:
        event_type = getattr(event, "event_type", "unknown")
        trace_id = getattr(event, "trace_id", None)

        attributes = {
            "event.type": event_type,
            "event.class": type(event).__name__,
        }

        if trace_id:
            attributes["event.trace_id"] = trace_id

        if hasattr(event, "timestamp"):
            attributes["event.timestamp"] = str(event.timestamp)

        span = self.start_span(
            name=f"event.{event_type}",
            attributes=attributes,
            parent_trace_id=trace_id,
        )

        return span

    def link_events(self, parent_event: Any, child_event: Any) -> None:
        parent_trace_id = getattr(parent_event, "trace_id", None)
        child_trace_id = getattr(child_event, "trace_id", None)

        if not parent_trace_id or not child_trace_id:
            return

        if not self._initialized or self._tracer is None:
            return

        try:
            parent_span = self._active_spans.get(parent_trace_id)
            if parent_span and parent_span._otel_span is not None:
                child_span = self.start_span(
                    name=f"event.link.{getattr(child_event, 'event_type', 'unknown')}",
                    attributes={
                        "link.parent_trace_id": parent_trace_id,
                        "link.child_trace_id": child_trace_id,
                    },
                )
                self.end_span(child_span)
        except Exception as e:
            logger.error(f"Failed to link events: {e}")

    def get_active_spans(self) -> List[SpanContext]:
        return list(self._active_spans.values())

    @property
    def is_initialized(self) -> bool:
        return self._initialized


_tracing_manager: Optional[TracingManager] = None


async def get_tracing_manager(
    service_name: str = "tradeagent",
    otlp_endpoint: str = "localhost:4317",
) -> TracingManager:
    """获取追踪管理器实例"""
    global _tracing_manager
    if _tracing_manager is None:
        _tracing_manager = TracingManager(
            service_name=service_name,
            otlp_endpoint=otlp_endpoint,
        )
        await _tracing_manager.initialize()
    return _tracing_manager
