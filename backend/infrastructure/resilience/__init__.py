"""
Resilience Infrastructure - 弹性基础设施
提供熔断、降级、重试等弹性能力
"""
from .circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitBreakerConfig,
    circuit,
    get_circuit_breaker
)
from .fallback import (
    FallbackResult,
    FallbackStrategy,
    PrimaryFallback,
    StaticValueFallback,
    AlternateFunctionFallback,
    FallbackChain,
    fallback,
    create_default_chain
)
from .retry import (
    RetryPolicy,
    RetryConfig,
    retry
)

__all__ = [
    # Circuit Breaker
    "CircuitBreaker",
    "CircuitState",
    "CircuitBreakerConfig",
    "circuit",
    "get_circuit_breaker",
    # Fallback
    "FallbackResult",
    "FallbackStrategy",
    "PrimaryFallback",
    "StaticValueFallback",
    "AlternateFunctionFallback",
    "FallbackChain",
    "fallback",
    "create_default_chain",
    # Retry
    "RetryPolicy",
    "RetryConfig",
    "retry"
]
