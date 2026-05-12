"""
Execution Service - 订单执行服务

功能：
- 交易所 API 对接（Binance/OKX）
- 订单管理（创建、查询、取消）
- 持仓管理
- 交易历史
"""

from .execution_engine import (
    ExecutionService,
    BaseExchangeAdapter,
    BinanceAdapter,
    Order,
    Position,
    OrderRequest,
    OrderResult,
    OrderSide,
    OrderType,
    OrderStatus,
    Exchange,
    get_execution_service,
    init_execution_service,
)

__all__ = [
    "ExecutionService",
    "BaseExchangeAdapter",
    "BinanceAdapter",
    "Order",
    "Position",
    "OrderRequest",
    "OrderResult",
    "OrderSide",
    "OrderType",
    "OrderStatus",
    "Exchange",
    "get_execution_service",
    "init_execution_service",
]
