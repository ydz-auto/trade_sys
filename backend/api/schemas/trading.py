"""
Trading Schemas - 完整交易相关模型
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum


class MarketType(str, Enum):
    """市场类型"""
    SPOT = "spot"           # 现货
    USDT_FUTURES = "usdt_futures"  # USDT合约
    COIN_FUTURES = "coin_futures"  # 币本位合约


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_MARKET = "stop_market"
    TAKE_PROFIT = "take_profit"
    TAKE_PROFIT_MARKET = "take_profit_market"


class PositionSide(str, Enum):
    LONG = "long"
    SHORT = "short"
    BOTH = "both"


class Exchange(str, Enum):
    BINANCE = "binance"
    OKX = "okx"


class TradingMode(str, Enum):
    AUTO = "auto"
    MANUAL = "manual"
    HYBRID = "hybrid"


class PositionMode(str, Enum):
    """持仓模式"""
    ISOLATED = "isolated"    # 逐仓
    CROSS = "cross"          # 全仓


class OrderRequest(BaseModel):
    """下单请求"""
    symbol: str = Field(..., description="交易对，如 BTC/USDT")
    side: OrderSide = Field(..., description="买入或卖出")
    order_type: OrderType = Field(default=OrderType.MARKET, description="订单类型")
    quantity: float = Field(..., description="数量")
    price: Optional[float] = Field(None, description="限价价格")
    exchange: Exchange = Field(default=Exchange.BINANCE, description="交易所")
    market_type: MarketType = Field(default=MarketType.SPOT, description="市场类型")
    
    # 杠杆和仓位
    leverage: int = Field(default=1, ge=1, le=125, description="杠杆倍数")
    position_mode: PositionMode = Field(default=PositionMode.ISOLATED, description="持仓模式")
    position_size_pct: float = Field(default=10.0, ge=1, le=100, description="仓位比例(%)")
    
    # 止盈止损
    stop_loss_pct: Optional[float] = Field(None, ge=0.1, le=50, description="止损比例(%)")
    take_profit_pct: Optional[float] = Field(None, ge=0.1, le=100, description="止盈比例(%)")
    
    # 高级
    reduce_only: bool = Field(default=False, description="只减仓")
    close_position: bool = Field(default=False, description="市价平仓")


class OrderResponse(BaseModel):
    """订单响应"""
    order_id: str
    symbol: str
    side: str
    quantity: float
    price: Optional[float] = None
    filled_quantity: float = 0
    avg_fill_price: Optional[float] = None
    status: str
    order_type: str
    market_type: str
    exchange: str
    leverage: int = 1
    position_size_pct: float = 10.0
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    created_at: str
    updated_at: Optional[str] = None


class PositionResponse(BaseModel):
    """持仓响应"""
    position_id: str
    symbol: str
    side: PositionSide
    quantity: float
    entry_price: float
    current_price: float
    mark_price: Optional[float] = None
    
    # 盈亏
    unrealized_pnl: float
    unrealized_pnl_pct: float
    realized_pnl: float = 0
    
    # 杠杆相关
    leverage: int
    margin: float
    margin_ratio: Optional[float] = None
    liquidation_price: Optional[float] = None
    
    # 市场信息
    market_type: MarketType
    exchange: Exchange
    
    # 止盈止损
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    
    # 状态
    opened_at: str
    updated_at: Optional[str] = None


class ClosePositionRequest(BaseModel):
    """平仓请求"""
    symbol: str
    quantity: Optional[float] = None
    order_type: OrderType = Field(default=OrderType.MARKET)
    price: Optional[float] = None
    exchange: Exchange = Field(default=Exchange.BINANCE)
    market_type: MarketType = Field(default=MarketType.USDT_FUTURES)


class TradingStatusResponse(BaseModel):
    """交易状态"""
    mode: TradingMode
    auto_approve_threshold: float
    
    # 汇总
    total_equity: float
    total_unrealized_pnl: float
    total_realized_pnl: float
    daily_pnl: float
    
    # 持仓
    positions: List[PositionResponse]
    total_position_value: float
    
    # 订单
    open_orders: List[OrderResponse]
    
    # 账户
    margin_balance: float
    available_balance: float
    
    # 风险
    total_leverage: float
    max_leverage: int


class SetTradingModeRequest(BaseModel):
    """设置交易模式"""
    mode: TradingMode
    auto_approve_threshold: Optional[float] = None


class SetLeverageRequest(BaseModel):
    """设置杠杆请求"""
    symbol: str
    leverage: int = Field(..., ge=1, le=125)
    market_type: MarketType = Field(default=MarketType.USDT_FUTURES)
    exchange: Exchange = Field(default=Exchange.BINANCE)


class SetStopLossTakeProfitRequest(BaseModel):
    """设置止盈止损"""
    symbol: str
    stop_loss_pct: Optional[float] = Field(None, ge=0.1, le=50)
    take_profit_pct: Optional[float] = Field(None, ge=0.1, le=100)
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    exchange: Exchange = Field(default=Exchange.BINANCE)
    market_type: MarketType = Field(default=MarketType.USDT_FUTURES)


class AdjustPositionRequest(BaseModel):
    """调整仓位"""
    symbol: str
    new_quantity: float = Field(..., gt=0)
    new_leverage: Optional[int] = Field(None, ge=1, le=125)
    exchange: Exchange = Field(default=Exchange.BINANCE)
    market_type: MarketType = Field(default=MarketType.USDT_FUTURES)


class HealthCheck(BaseModel):
    """健康检查"""
    status: str
    exchanges: dict
    market_types: dict
    timestamp: str


class ExchangeAccount(BaseModel):
    """交易所账户信息"""
    exchange: Exchange
    market_type: MarketType
    balance: float
    available_balance: float
    margin_balance: float
    unrealized_pnl: float
    positions_count: int
    leverage: Optional[int] = None
    position_mode: Optional[PositionMode] = None


class AccountBalancesResponse(BaseModel):
    """账户余额响应"""
    total_equity: float
    accounts: List[ExchangeAccount]
