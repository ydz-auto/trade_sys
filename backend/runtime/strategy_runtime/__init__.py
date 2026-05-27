"""
Strategy Runtime - 策略运行时层

核心功能：
1. 策略定义与注册
2. 策略状态管理
3. 策略信号生成
4. 多策略协调
5. 策略与特征层集成
"""
from .runtime import StrategyRuntime, get_strategy_runtime
from .strategy_state import StrategyStateManager, StrategyInstanceState
from .models import (
    StrategySignal,
    StrategyAction,
    StrategyStatus,
    StrategyType,
    StrategyDefinition,
)

__all__ = [
    "StrategyRuntime",
    "get_strategy_runtime",
    "StrategyStateManager",
    "StrategyInstanceState",
    "StrategySignal",
    "StrategyAction",
    "StrategyStatus",
    "StrategyType",
    "StrategyDefinition",
]
