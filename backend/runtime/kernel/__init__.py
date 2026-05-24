"""
runtime.kernel - 交易内核包

公共模块路径:
  - runtime.kernel.core: RuntimeKernel, KernelMode, RawEvent, StateTrajectory
  - runtime.kernel.snapshot.checkpoint: CheckpointManager
  - runtime.kernel.snapshot.state_hash: compute_runtime_hash, verify_runtime_hash
  - runtime.kernel.snapshot.recovery_coordinator: RecoveryCoordinator
"""

from runtime.kernel.base import BaseRuntime, RuntimeConfig, RuntimeContext
from runtime.kernel.core import KernelMode, RawEvent, RuntimeKernel, StateTrajectory

__all__ = [
    "BaseRuntime",
    "KernelMode",
    "RawEvent",
    "RuntimeConfig",
    "RuntimeContext",
    "RuntimeKernel",
    "StateTrajectory",
]
