"""
Resilience Infrastructure - 弹性基础设施
提供熔断、降级、重试等弹性能力
"""
from .circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitBreakerConfig,
    circuit
)
from .fallback import (
    FallbackStrategy,
    FallbackChain,
    fallback
)
from .retry import (
    RetryPolicy,
    RetryConfig,
    retry
)

__all__ = [
    "CircuitBreaker",
    "CircuitState",
    "CircuitBreakerConfig",
    "circuit",
    "FallbackStrategy",
    "FallbackChain",
    "fallback",
    "RetryPolicy",
    "RetryConfig",
    "retry"
]
