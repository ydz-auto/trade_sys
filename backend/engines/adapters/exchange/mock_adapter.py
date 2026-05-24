from typing import Dict, List, Optional
from datetime import datetime
import uuid

from domain.execution.models import (
    Order,
    OrderRequest,
    OrderResult,
    Position,
    Exchange,
    OrderSide,
    OrderType,
    OrderStatus,
    MarketType,
)
from engines.adapters.exchange.base_adapter import BaseExchangeAdapter
from infrastructure.logging import get_logger

logger = get_logger("execution_service.adapters.mock")


class MockAdapter(BaseExchangeAdapter):

    def __init__(self, initial_balance: Dict[str, float] = None):
        super().__init__(Exchange.BINANCE)
        self._orders: Dict[str, Order] = {}
        self._positions: Dict[str, Position] = {}
        self._balance = initial_balance or {
            "USDT": 10000.0,
            "BTC": 0.5,
            "ETH": 5.0,
        }
        self._prices: Dict[str, float] = {
            "BTC/USDT": 50000.0,
            "ETH/USDT": 3000.0,
        }

    async def connect(self) -> bool:
        self._connected = True
        logger.info("Mock adapter connected")
        return True

    async def disconnect(self) -> None:
        self._connected = False
        logger.info("Mock adapter disconnected")

    async def create_order(self, request: OrderRequest) -> OrderResult:
        if not self._connected:
            return OrderResult(success=False, error="Not connected")

        order_id = f"mock_{uuid.uuid4().hex[:12]}"
        price = request.price or self._prices.get(request.symbol, 50000.0)

        order = Order(
            order_id=order_id,
            symbol=request.symbol,
            exchange=self.exchange,
            side=request.side,
            order_type=request.order_type,
            quantity=request.quantity,
            price=price,
            status=OrderStatus.FILLED,
            filled_quantity=request.quantity,
            average_price=price,
            market_type=request.market_type,
            metadata={
                "client_order_id": request.client_order_id,
                "mock": True,
            },
        )

        self._orders[order_id] = order
        self._update_position(order)
        self._update_balance(order)

        logger.info(f"[MOCK] Order created: {order_id} {request.side.value} {request.quantity} {request.symbol} @ {price}")

        return OrderResult(success=True, order=order)

    def _update_position(self, order: Order):
        symbol = order.symbol
        if symbol not in self._positions:
            self._positions[symbol] = Position(
                symbol=symbol,
                exchange=self.exchange,
                quantity=0,
                average_price=0,
                market_type=order.market_type,
            )

        pos = self._positions[symbol]

        if order.side == OrderSide.BUY:
            total_cost = pos.quantity * pos.average_price + order.filled_quantity * order.average_price
            pos.quantity += order.filled_quantity
            pos.average_price = total_cost / pos.quantity if pos.quantity > 0 else 0
        else:
            pos.quantity -= order.filled_quantity

        if abs(pos.quantity) < 1e-8:
            pos.quantity = 0
            pos.average_price = 0

        pos.updated_at = datetime.now()

    def _update_balance(self, order: Order):
        if "/" in order.symbol:
            base, quote = order.symbol.split("/")
        elif order.symbol.endswith("USDT"):
            base = order.symbol[:-4]
            quote = "USDT"
        elif order.symbol.endswith("BTC"):
            base = order.symbol[:-3]
            quote = "BTC"
        else:
            base = order.symbol
            quote = "USDT"

        cost = order.filled_quantity * order.average_price

        if order.side == OrderSide.BUY:
            if quote in self._balance:
                self._balance[quote] -= cost
            if base in self._balance:
                self._balance[base] += order.filled_quantity
            else:
                self._balance[base] = order.filled_quantity
        else:
            if base in self._balance:
                self._balance[base] -= order.filled_quantity
            if quote in self._balance:
                self._balance[quote] += cost

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        if order_id in self._orders:
            order = self._orders[order_id]
            if order.status in [OrderStatus.PENDING, OrderStatus.SUBMITTED]:
                order.status = OrderStatus.CANCELLED
                order.updated_at = datetime.now()
                logger.info(f"[MOCK] Order cancelled: {order_id}")
                return True
        return False

    async def get_order(self, order_id: str, symbol: str) -> Optional[Order]:
        return self._orders.get(order_id)

    async def get_positions(self) -> List[Position]:
        return [p for p in self._positions.values() if abs(p.quantity) > 1e-8]

    async def get_balance(self) -> Dict[str, float]:
        return self._balance.copy()

    async def get_market_price(self, symbol: str) -> Optional[float]:
        return self._prices.get(symbol)

    def set_price(self, symbol: str, price: float):
        self._prices[symbol] = price
