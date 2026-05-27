"""
Market State Machine
市场状态机

提供统一的市场状态管理，用于交易决策。

Key Components:
- RegimeType: 市场状态枚举
- MarketState: 不可变的市场状态对象
- MarketStateMachine: 事件驱动的状态转换引擎
"""

from domain.market_state.state import (
    RegimeType,
    LiquidityState,
    PressureState,
    VolatilityState,
    TrendState,
    MarketState,
)
from domain.market_state.machine import MarketStateMachine

__all__ = [
    "RegimeType",
    "LiquidityState",
    "PressureState",
    "VolatilityState",
    "TrendState",
    "MarketState",
    "MarketStateMachine",
]
