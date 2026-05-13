"""
Execution Domain

执行领域模块
"""

from domain.execution.config import (
    OrderTypeConfig,
    SlippageConfig,
    FeeConfig,
    ExchangeFeeConfig,
    ContractType,
    ExecutionRuntimeConfig,
    EXECUTION_DEFAULTS,
    EXECUTION_SCHEMA,
)
from domain.execution.models import (
    OrderSide,
    OrderType,
    OrderStatus,
    Exchange,
    MarketType,
    TimeInForce,
    Order,
    OrderRequest,
    OrderResult,
    OrderIntent,
    Position,
    OrderCreated,
    OrderUpdated,
    OrderFilled,
    PositionUpdated,
)
from domain.execution.utils import (
    ExpectedReturn,
    FeeCalculator,
)

__all__ = [
    "OrderTypeConfig",
    "SlippageConfig",
    "FeeConfig",
    "ExchangeFeeConfig",
    "ContractType",
    "ExecutionRuntimeConfig",
    "EXECUTION_DEFAULTS",
    "EXECUTION_SCHEMA",
    "OrderSide",
    "OrderType",
    "OrderStatus",
    "Exchange",
    "MarketType",
    "TimeInForce",
    "Order",
    "OrderRequest",
    "OrderResult",
    "OrderIntent",
    "Position",
    "OrderCreated",
    "OrderUpdated",
    "OrderFilled",
    "PositionUpdated",
    "ExpectedReturn",
    "FeeCalculator",
]
