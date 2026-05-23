"""
Runtime State Module

核心组件:
- RuntimeStateStore: 统一系统状态
"""
from .store import (
    StateSnapshot,
    RuntimeStateStore,
    get_runtime_state_store,
    get_state,
)

__all__ = [
    "StateSnapshot",
    "RuntimeStateStore",
    "get_runtime_state_store",
    "get_state",
]
