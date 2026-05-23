"""
Runtime - 运行时核心

Runtime 收敛的核心组件：
- P0.1: AuthoritySystem (时钟、可用性、顺序)
- P0.2: GuardSystem (拦截违规)
- P0.3: RuntimeKernel (单一入口)
- P0.4: DeterministicReplay (验证)
"""

from runtime.authority import (
    ClockAuthority,
    ClockMode,
    AvailabilityAuthority,
    LatencyModel,
    FixedLatencyModel,
    OrderingAuthority,
    AuthoritySystem,
)

from runtime.guards import (
    GuardViolation,
    BaseGuard,
    AvailabilityGuard,
    OrderingGuard,
    MutationGuard,
    PartialCandleGuard,
    DuplicateGuard,
    ClockGuard,
    GuardSystem,
)

from runtime.kernel import (
    KernelMode,
    RawEvent,
    StateTrajectory,
    RuntimeKernel,
)

__all__ = [
    # Authority
    "ClockAuthority",
    "ClockMode",
    "AvailabilityAuthority",
    "LatencyModel",
    "FixedLatencyModel",
    "OrderingAuthority",
    "AuthoritySystem",
    
    # Guards
    "GuardViolation",
    "BaseGuard",
    "AvailabilityGuard",
    "OrderingGuard",
    "MutationGuard",
    "PartialCandleGuard",
    "DuplicateGuard",
    "ClockGuard",
    "GuardSystem",
    
    # Kernel
    "KernelMode",
    "RawEvent",
    "StateTrajectory",
    "RuntimeKernel",
]
