"""
Market State Machine
市场状态机

提供统一的市场状态管理，用于交易决策。

Key Components:
- RegimeType: 市场状态枚举
- MarketState: 不可变的市场状态对象
- MarketStateMachine: 事件驱动的状态转换引擎
- MarketContext: 统一市场上下文（单一真相源）
- MarketContextAuthority: 市场上下文权威层
- TimeframeContext: 单个时间周期的上下文
- 分层上下文类（Regime/Price/Volatility/Liquidity/Flow/Derivatives/CrossMarket/RiskFlags）
"""

from domain.market_state.state import (
    MarketRegime,
    RegimeType,
    LiquidityState,
    PressureState,
    VolatilityState,
    TrendState,
    MarketState,
)
from domain.market_state.machine import MarketStateMachine
from domain.market_state.context import (
    STANDARD_TIMEFRAMES,
    MarketContext,
    MarketContextAuthority,
)
from domain.market_state.layers import (
    TrendState as TimeframeTrendState,
    MomentumDirection,
    VolatilityState as TimeframeVolatilityState,
    VolumeState,
    FlowPressure,
    LiquidityLevel,
    TimeframeContext,
    RegimeContext,
    PriceContext,
    VolatilityContext,
    LiquidityContext,
    FlowContext,
    DerivativesContext,
    CrossMarketContext,
    RiskFlags,
)

__all__ = [
    "MarketRegime",
    "RegimeType",
    "LiquidityState",
    "PressureState",
    "VolatilityState",
    "TrendState",
    "MarketState",
    "MarketStateMachine",
    
    # 统一上下文（核心）
    "STANDARD_TIMEFRAMES",
    "MarketContext",
    "MarketContextAuthority",
    
    # 分层上下文（新架构）
    "TimeframeTrendState",
    "MomentumDirection",
    "TimeframeVolatilityState",
    "VolumeState",
    "FlowPressure",
    "LiquidityLevel",
    "TimeframeContext",
    "RegimeContext",
    "PriceContext",
    "VolatilityContext",
    "LiquidityContext",
    "FlowContext",
    "DerivativesContext",
    "CrossMarketContext",
    "RiskFlags",
]
