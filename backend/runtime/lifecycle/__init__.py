"""
Runtime Lifecycle Module - Runtime 生命周期模块

核心组件:
- RuntimeHealthSystem: 健康治理
- RuntimeStateMachine: 状态机
"""
from .runtime_health import (
    HealthStatus,
    AlertLevel,
    HealthCheck,
    HealthAlert,
    HealthMetrics,
    RuntimeHealthSystem,
    get_health_system,
)

from .state_machine import (
    RuntimeState,
    TransitionResult,
    StateTransition,
    StateMachineConfig,
    RuntimeStateMachine,
    get_state_machine,
)

__all__ = [
    "HealthStatus",
    "AlertLevel",
    "HealthCheck",
    "HealthAlert",
    "HealthMetrics",
    "RuntimeHealthSystem",
    "get_health_system",
    
    "RuntimeState",
    "TransitionResult",
    "StateTransition",
    "StateMachineConfig",
    "RuntimeStateMachine",
    "get_state_machine",
]
