"""
Runtime Shared Components - 统一的运行时组件

所有 Runtime 共享的组件：
- lifecycle: 生命周期管理
- metrics: 指标收集
- consumer: Kafka 消费者
- publisher: Kafka 发布者
- healthcheck: 健康检查
"""

from runtime.shared.lifecycle import RuntimeLifecycle, RuntimePhase
from runtime.shared.metrics import RuntimeMetrics, TimingContext
from infrastructure.messaging.runtime_consumer import RuntimeConsumer, ConsumerConfig
from infrastructure.messaging.runtime_publisher import RuntimePublisher, PublisherConfig
from runtime.shared.healthcheck import RuntimeHealthCheck, HealthStatus, HealthCheckResult

__all__ = [
    "RuntimeLifecycle",
    "RuntimePhase",
    "RuntimeMetrics",
    "TimingContext",
    "RuntimeConsumer",
    "ConsumerConfig",
    "RuntimePublisher",
    "PublisherConfig",
    "RuntimeHealthCheck",
    "HealthStatus",
    "HealthCheckResult",
]
