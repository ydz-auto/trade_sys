"""
Runtime Module - 统一运行时模块

提供：
1. 统一时钟系统 (Clock)
2. 统一运行时引擎 (RuntimeEngine)
3. 四种运行模式支持 (live/paper/replay/backtest)
4. 系统治理 (Governor, CircuitBreaker, Degradation)
5. 运行时恢复 (RuntimeRecovery)
6. 分布式治理 (DistributedRuntimeGovernance)
"""

from infrastructure.runtime.clock import (
    Clock,
    ClockMode,
    ClockConfig,
    get_clock,
    set_clock,
    now,
    timestamp,
    clock_sleep,
    clock_sleep_async,
    use_clock,
)

from infrastructure.runtime.engine import (
    RuntimeEngine,
    RuntimeMode,
    RuntimeConfig,
    RuntimeState,
    create_live_runtime,
    create_paper_runtime,
    create_replay_runtime,
    create_backtest_runtime,
)

from infrastructure.runtime.priority_queue import (
    EventPriority,
    PrioritizedEvent,
    PriorityEventQueue,
)

from infrastructure.runtime.degradation import (
    RuntimeMode as GovernorMode,
    DegradationConfig,
    DegradationController,
    DEGRADATION_PROFILES,
)

from infrastructure.runtime.circuit_breaker_manager import (
    CircuitState,
    CircuitBreakerConfig,
    CircuitBreaker,
    CircuitBreakerManager,
    CircuitBreakerOpenError,
    get_circuit_breaker_manager,
)

from infrastructure.runtime.subscription_manager import (
    Subscription,
    SubscriptionManager,
    TopicRegistry,
)

from infrastructure.runtime.governor import (
    GovernorState,
    GovernorConfig,
    RuntimeGovernor,
    get_runtime_governor,
)

from infrastructure.runtime.recovery import (
    RecoveryState,
    RecoveryCheckpoint,
    RecoveryConfig,
    RuntimeRecovery,
    get_runtime_recovery,
)

from infrastructure.runtime.distributed_governance import (
    NodeState,
    Role,
    NodeInfo,
    DistributedGovernanceConfig,
    DistributedRuntimeGovernance,
    get_distributed_governance,
)

__all__ = [
    "Clock",
    "ClockMode",
    "ClockConfig",
    "get_clock",
    "set_clock",
    "now",
    "timestamp",
    "clock_sleep",
    "clock_sleep_async",
    "use_clock",
    "RuntimeEngine",
    "RuntimeMode",
    "RuntimeConfig",
    "RuntimeState",
    "create_live_runtime",
    "create_paper_runtime",
    "create_replay_runtime",
    "create_backtest_runtime",
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
    "GovernorState",
    "GovernorConfig",
    "RuntimeGovernor",
    "get_runtime_governor",
    "RecoveryState",
    "RecoveryCheckpoint",
    "RecoveryConfig",
    "RuntimeRecovery",
    "get_runtime_recovery",
    "NodeState",
    "Role",
    "NodeInfo",
    "DistributedGovernanceConfig",
    "DistributedRuntimeGovernance",
    "get_distributed_governance",
]
