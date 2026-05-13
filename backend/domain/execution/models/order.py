"""
Order Models

订单相关模型
"""

from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

from domain.execution.models.enums import (
    OrderSide,
    OrderType,
    OrderStatus,
    Exchange,
    MarketType,
    TimeInForce,
)


@dataclass
class Order:
    """订单"""
    order_id: str
    symbol: str
    exchange: Exchange
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    average_price: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    market_type: MarketType = MarketType.SPOT
    client_order_id: Optional[str] = None
    exchange_order_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "exchange": self.exchange.value,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "quantity": self.quantity,
            "price": self.price,
            "status": self.status.value,
            "filled_quantity": self.filled_quantity,
            "average_price": self.average_price,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "error": self.error,
            "metadata": self.metadata,
            "market_type": self.market_type.value,
            "client_order_id": self.client_order_id,
            "exchange_order_id": self.exchange_order_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Order":
        return cls(
            order_id=data["order_id"],
            symbol=data["symbol"],
            exchange=Exchange(data["exchange"]),
            side=OrderSide(data["side"]),
            order_type=OrderType(data["order_type"]),
            quantity=data["quantity"],
            price=data.get("price"),
            status=OrderStatus(data.get("status", "pending")),
            filled_quantity=data.get("filled_quantity", 0.0),
            average_price=data.get("average_price"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.now(),
            error=data.get("error"),
            metadata=data.get("metadata", {}),
            market_type=MarketType(data.get("market_type", "spot")),
            client_order_id=data.get("client_order_id"),
            exchange_order_id=data.get("exchange_order_id"),
        )


@dataclass
class OrderRequest:
    """订单请求"""
    symbol: str
    exchange: Exchange
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    client_order_id: Optional[str] = None
    market_type: MarketType = MarketType.SPOT
    time_in_force: TimeInForce = TimeInForce.GTC
    reduce_only: bool = False
    leverage: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "exchange": self.exchange.value,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "quantity": self.quantity,
            "price": self.price,
            "stop_price": self.stop_price,
            "client_order_id": self.client_order_id,
            "market_type": self.market_type.value,
            "time_in_force": self.time_in_force.value,
            "reduce_only": self.reduce_only,
            "leverage": self.leverage,
        }


@dataclass
class OrderResult:
    """订单结果"""
    success: bool
    order: Optional[Order] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "order": self.order.to_dict() if self.order else None,
            "error": self.error,
        }


@dataclass
class OrderIntent:
    """执行意图

    Signal 到 Exchange Order 的中间层
    包含风控参数和执行参数
    """
    intent_id: str
    symbol: str
    side: OrderSide
    quantity: float
    exchange: Exchange = Exchange.BINANCE
    market_type: MarketType = MarketType.SPOT

    max_leverage: int = 1
    max_position_value: float = 10000.0
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None

    time_in_force: TimeInForce = TimeInForce.GTC
    reduce_only: bool = False

    signal_id: Optional[str] = None
    strategy_id: Optional[str] = None
    confidence: float = 0.0

    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "quantity": self.quantity,
            "exchange": self.exchange.value,
            "market_type": self.market_type.value,
            "max_leverage": self.max_leverage,
            "max_position_value": self.max_position_value,
            "stop_loss_pct": self.stop_loss_pct,
            "take_profit_pct": self.take_profit_pct,
            "time_in_force": self.time_in_force.value,
            "reduce_only": self.reduce_only,
            "signal_id": self.signal_id,
            "strategy_id": self.strategy_id,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
        }

    def to_order_request(self, order_type: OrderType = OrderType.MARKET, price: Optional[float] = None) -> OrderRequest:
        """转换为订单请求"""
        return OrderRequest(
            symbol=self.symbol,
            exchange=self.exchange,
            side=self.side,
            order_type=order_type,
            quantity=self.quantity,
            price=price,
            market_type=self.market_type,
            time_in_force=self.time_in_force,
            reduce_only=self.reduce_only,
            leverage=self.max_leverage,
        )
