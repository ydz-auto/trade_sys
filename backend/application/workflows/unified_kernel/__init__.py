"""
Unified Runtime Interface - 三范式统一运行时接口

统一的 Domain Kernel + 三个 Runtime Adapter

核心设计原则：
1. 唯一的业务真相在 Domain Kernel
2. 三个范式（LIVE/REPLAY/RESEARCH）只是三个 Adapter
3. 策略完全不知道是 LIVE/REPLAY/RESEARCH
4. 完全禁止策略分叉
"""

from application.workflows.unified_kernel.runtime_contract import (
    RuntimeContract,
    RuntimeMode,
    RuntimeLifecycle,
    RuntimeAdapter,
    create_runtime_adapter,
)
from application.workflows.unified_kernel.domain_kernel import (
    DomainKernel,
    DomainKernelConfig,
)
from application.workflows.unified_kernel.adapters import (
    LiveRuntimeAdapter,
    ReplayRuntimeAdapter,
    ResearchRuntimeAdapter,
)

__all__ = [
    "RuntimeContract",
    "RuntimeMode",
    "RuntimeLifecycle",
    "RuntimeAdapter",
    "create_runtime_adapter",
    "DomainKernel",
    "DomainKernelConfig",
    "LiveRuntimeAdapter",
    "ReplayRuntimeAdapter",
    "ResearchRuntimeAdapter",
]
