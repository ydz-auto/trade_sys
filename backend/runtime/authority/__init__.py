"""
Runtime Authority System - 运行时权威系统

核心组件：
- ClockAuthority: 时钟权威（唯一时间源）
- AvailabilityAuthority: 可用性权威（自动计算可用时间）
- OrderingAuthority: 顺序权威（保证事件因果顺序）
- AuthoritySystem: 组合入口（一站式事件处理）

设计原则：
- 不允许手填时间语义
- 必须由 Authority 自动生成
- 单点控制，全局一致
"""

from runtime.authority.clock_authority import (
    ClockAuthority,
    ClockMode,
)
from runtime.authority.availability_authority import (
    AvailabilityAuthority,
    LatencyModel,
    FixedLatencyModel,
)
from runtime.authority.ordering_authority import (
    OrderingAuthority,
)
from runtime.authority.authority_system import (
    AuthoritySystem,
)

__all__ = [
    "ClockAuthority",
    "ClockMode",
    "AvailabilityAuthority",
    "LatencyModel",
    "FixedLatencyModel",
    "OrderingAuthority",
    "AuthoritySystem",
]
