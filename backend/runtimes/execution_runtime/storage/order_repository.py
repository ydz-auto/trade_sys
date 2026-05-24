from typing import Dict, List, Optional
import json

from domain.execution.models import Order, OrderStatus
from infrastructure.persistence.state.types import StateType
from infrastructure.persistence.state.manager import StateManager, get_state_manager
from infrastructure.logging import get_logger

logger = get_logger("execution_service.storage.order_repository")


class OrderRepository:

    def __init__(self, state_manager: StateManager = None):
        self._state_manager = state_manager or get_state_manager()

    async def save(self, order: Order) -> None:
        key = order.order_id
        self._state_manager.set_state(
            StateType.ORDER,
            order.to_dict(),
            key=key,
            persist=True,
        )
        logger.debug(f"Order saved: {order.order_id}")

    async def get(self, order_id: str) -> Optional[Order]:
        data = self._state_manager.get_state(StateType.ORDER, key=order_id)
        if data:
            return Order.from_dict(data)
        return None

    async def get_all(self) -> List[Order]:
        data = self._state_manager.get_state(StateType.ORDER) or {}
        return [Order.from_dict(o) for o in data.values() if isinstance(o, dict)]

    async def get_by_status(self, status: OrderStatus) -> List[Order]:
        orders = await self.get_all()
        return [o for o in orders if o.status == status]

    async def get_active_orders(self) -> List[Order]:
        active_statuses = [
            OrderStatus.PENDING,
            OrderStatus.SUBMITTED,
            OrderStatus.PARTIALLY_FILLED,
        ]
        orders = await self.get_all()
        return [o for o in orders if o.status in active_statuses]

    async def delete(self, order_id: str) -> None:
        self._state_manager.delete_state(StateType.ORDER, key=order_id)
        logger.debug(f"Order deleted: {order_id}")

    async def update_status(
        self,
        order_id: str,
        status: OrderStatus,
        filled_quantity: float = None,
        average_price: float = None,
    ) -> Optional[Order]:
        order = await self.get(order_id)
        if order:
            order.status = status
            if filled_quantity is not None:
                order.filled_quantity = filled_quantity
            if average_price is not None:
                order.average_price = average_price
            await self.save(order)
            return order
        return None

    async def get_history(self, limit: int = 100) -> List[Order]:
        orders = await self.get_all()
        return sorted(orders, key=lambda o: o.created_at, reverse=True)[:limit]
