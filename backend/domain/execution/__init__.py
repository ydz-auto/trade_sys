"""
Execution Domain - 执行领域核心

这个模块只包含核心领域模型和规则，不包含业务逻辑。

包含：
- models: 订单、持仓、事件模型
- config: 执行配置
- trading_mode: 交易模式
- utils: 费用计算等工具

业务逻辑（如执行分析、智能执行、订单拆分、滑点控制）请使用:
    services.execution_service.quality
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
