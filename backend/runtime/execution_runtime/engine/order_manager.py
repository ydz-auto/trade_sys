from typing import Dict, List, Optional
from datetime import datetime
import uuid

from domain.execution.models import (
    Order,
    OrderRequest,
    OrderResult,
    OrderStatus,
    Exchange,
)
from infrastructure.logging import get_logger

logger = get_logger("execution_service.order_manager")


class OrderManager:

    def __init__(self):
        self._orders: Dict[str, Order] = {}
        self._pending_orders: Dict[str, Order] = {}

    def create_order(self, request: OrderRequest, exchange_order_id: str = None) -> Order:
        order_id = f"ord_{uuid.uuid4().hex[:12]}"

        order = Order(
            order_id=order_id,
            symbol=request.symbol,
            exchange=request.exchange,
            side=request.side,
            order_type=request.order_type,
            quantity=request.quantity,
            price=request.price,
            status=OrderStatus.PENDING,
            market_type=request.market_type,
            client_order_id=request.client_order_id,
            exchange_order_id=exchange_order_id,
            metadata={
                "leverage": request.leverage,
                "reduce_only": request.reduce_only,
                "time_in_force": request.time_in_force.value,
            },
        )

        self._orders[order_id] = order
        self._pending_orders[order_id] = order

        logger.info(f"Order created: {order_id} {request.side.value} {request.quantity} {request.symbol}")
        return order

    def update_order_status(
        self,
        order_id: str,
        status: OrderStatus,
        filled_quantity: float = None,
        average_price: float = None,
        error: str = None,
    ) -> Optional[Order]:
        if order_id not in self._orders:
            logger.warning(f"Order not found: {order_id}")
            return None

        order = self._orders[order_id]
        old_status = order.status

        order.status = status
        order.updated_at = datetime.now()

        if filled_quantity is not None:
            order.filled_quantity = filled_quantity

        if average_price is not None:
            order.average_price = average_price

        if error is not None:
            order.error = error

        if status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.FAILED]:
            if order_id in self._pending_orders:
                del self._pending_orders[order_id]

        logger.info(f"Order {order_id} status changed: {old_status.value} -> {status.value}")
        return order

    def get_order(self, order_id: str) -> Optional[Order]:
        return self._orders.get(order_id)

    def get_orders_by_symbol(self, symbol: str, exchange: Exchange = None) -> List[Order]:
        orders = [o for o in self._orders.values() if o.symbol == symbol]
        if exchange:
            orders = [o for o in orders if o.exchange == exchange]
        return orders

    def get_pending_orders(self) -> List[Order]:
        return list(self._pending_orders.values())

    def get_active_orders(self) -> List[Order]:
        active_statuses = [OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED]
        return [o for o in self._orders.values() if o.status in active_statuses]

    def get_order_history(self, limit: int = 100) -> List[Order]:
        orders = sorted(
            self._orders.values(),
            key=lambda o: o.created_at,
            reverse=True,
        )
        return orders[:limit]

    def cancel_order(self, order_id: str) -> bool:
        if order_id in self._pending_orders:
            order = self._pending_orders[order_id]
            order.status = OrderStatus.CANCELLED
            order.updated_at = datetime.now()
            del self._pending_orders[order_id]
            logger.info(f"Order cancelled: {order_id}")
            return True
        return False

    def get_order_count(self) -> int:
        return len(self._orders)

    def get_pending_count(self) -> int:
        return len(self._pending_orders)
