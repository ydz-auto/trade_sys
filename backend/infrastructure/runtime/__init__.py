"""
Runtime Infrastructure Module - 向后兼容 re-export

所有模块已迁移至 infrastructure/ 顶层，此文件仅保留向后兼容的 re-export。
"""

from infrastructure.priority_queue import (
    EventPriority,
    PrioritizedEvent,
    PriorityEventQueue,
)

from infrastructure.degradation import (
    RuntimeMode as GovernorMode,
    DegradationConfig,
    DegradationController,
    DEGRADATION_PROFILES,
)

from infrastructure.circuit_breaker_manager import (
    CircuitState,
    CircuitBreakerConfig,
    CircuitBreaker,
    CircuitBreakerManager,
    CircuitBreakerOpenError,
    get_circuit_breaker_manager,
)

from infrastructure.subscription_manager import (
    Subscription,
    SubscriptionManager,
    TopicRegistry,
)

__all__ = [
    "EventPriority",
    "PrioritizedEvent",
    "PriorityEventQueue",
    "GovernorMode",
    "DegradationConfig",
    "DegradationController",
    "DEGRADATION_PROFILES",
    "CircuitState",
    "CircuitBreakerConfig",
    "CircuitBreaker",
    "CircuitBreakerManager",
    "CircuitBreakerOpenError",
    "get_circuit_breaker_manager",
    "Subscription",
    "SubscriptionManager",
    "TopicRegistry",
]
