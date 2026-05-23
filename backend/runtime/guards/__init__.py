"""
Runtime Guard System - 运行时守卫系统

核心守卫：
- AvailabilityGuard: 禁止未来数据
- OrderingGuard: 禁止乱序
- MutationGuard: 禁止修改 Event
- PartialCandleGuard: 禁止未完成 K 线
- DuplicateGuard: 去重
- ReplayParityGuard: Replay=Live 验证
- ClockGuard: 强制统一时间
- DependencyGuard: 检查特征依赖

设计原则：
- 守卫是拦截器模式
- 任何违反都抛出 GuardViolation
- 默认拒绝，显式允许
"""

from runtime.guards.base_guard import (
    GuardViolation,
    BaseGuard,
)
from runtime.guards.availability_guard import AvailabilityGuard
from runtime.guards.ordering_guard import OrderingGuard
from runtime.guards.mutation_guard import MutationGuard
from runtime.guards.partial_candle_guard import PartialCandleGuard
from runtime.guards.duplicate_guard import DuplicateGuard
from runtime.guards.clock_guard import ClockGuard
from runtime.guards.guard_system import GuardSystem

__all__ = [
    "GuardViolation",
    "BaseGuard",
    "AvailabilityGuard",
    "OrderingGuard",
    "MutationGuard",
    "PartialCandleGuard",
    "DuplicateGuard",
    "ClockGuard",
    "GuardSystem",
]
