"""
Replay Runtime Models - 回测运行时模型集合

包含完整的回测模型：
- FeeModel (手续费)
- SlippageModel (滑点)
- LiquidationModel (爆仓)
- FundingModel (资金费)
- BacktestExecutionEngine (完整回测执行引擎)
"""

from .fee_model import (
    FeeModel,
    FeeResult,
    FeeType,
    Exchange,
    calculate_fees
)

from .slippage import (
    SlippageModel,
    SlippageResult,
    OrderType,
    calculate_slippage
)

from .liquidation import (
    LiquidationModel,
    LiquidationResult,
    LiquidationStatus,
    check_liquidation
)

from .funding import (
    FundingModel,
    FundingResult,
    calculate_funding
)

from .backtest_engine import (
    BacktestExecutionConfig,
    TradeExecutionResult,
    BacktestExecutionEngine,
    OrderSide,
    create_backtest_engine
)

__all__ = [
    # Fee Model
    "FeeModel",
    "FeeResult",
    "FeeType",
    "Exchange",
    "calculate_fees",
    # Slippage Model
    "SlippageModel",
    "SlippageResult",
    "OrderType",
    "calculate_slippage",
    # Liquidation Model
    "LiquidationModel",
    "LiquidationResult",
    "LiquidationStatus",
    "check_liquidation",
    # Funding Model
    "FundingModel",
    "FundingResult",
    "calculate_funding",
    # Backtest Engine
    "BacktestExecutionConfig",
    "TradeExecutionResult",
    "BacktestExecutionEngine",
    "OrderSide",
    "create_backtest_engine",
]
