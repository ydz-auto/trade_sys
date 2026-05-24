"""
Execution Enums

执行相关枚举定义
"""

from enum import Enum


class OrderSide(str, Enum):
    """订单方向"""
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """订单类型"""
    MARKET = "market"
    LIMIT = "limit"
    STOP_MARKET = "stop_market"
    STOP_LIMIT = "stop_limit"
    TAKE_PROFIT = "take_profit"
    TAKE_PROFIT_LIMIT = "take_profit_limit"


class OrderStatus(str, Enum):
    """订单状态"""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    FAILED = "failed"
    EXPIRED = "expired"


class Exchange(str, Enum):
    """交易所"""
    BINANCE = "binance"
    OKX = "okx"
    COINBASE = "coinbase"


class MarketType(str, Enum):
    """市场类型"""
    SPOT = "spot"
    USDT_FUTURES = "usdt_futures"
    COIN_FUTURES = "coin_futures"
    SWAP = "swap"


class TimeInForce(str, Enum):
    """订单有效期类型"""
    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"
    GTX = "GTX"
