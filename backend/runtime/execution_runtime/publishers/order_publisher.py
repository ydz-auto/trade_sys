from typing import Dict, Any, Optional

from domain.execution.models import Order
from domain.execution.models.events import OrderCreated, OrderFilled, PositionUpdated
from infrastructure.logging import get_logger
from infrastructure.messaging.broker import get_broker
from infrastructure.messaging.topics import Topics
from infrastructure.config.defaults.infrastructure.middleware import KAFKA_BOOTSTRAP_SERVERS

logger = get_logger("execution_service.publishers.order")


class OrderPublisher:

    def __init__(self, broker=None):
        self._broker = broker

    async def _get_broker(self):
        if self._broker is None:
            bootstrap_servers = KAFKA_BOOTSTRAP_SERVERS
            self._broker = get_broker(bootstrap_servers)
        return self._broker

    async def publish_order_created(self, order: Order) -> None:
        event = OrderCreated(order=order)
        await self._publish("execution.orders.created", event.to_dict())
        logger.info(f"Published order_created: {order.order_id}")

    async def publish_order_updated(self, order: Order, old_status: str, new_status: str) -> None:
        from infrastructure.messaging.schema.base_event import OrderEvent, EventSource
        event = OrderEvent(
            source=EventSource.EXECUTION_SERVICE,
            symbol=order.symbol if hasattr(order, "symbol") else "BTCUSDT",
            event_time_ms=order.created_at if isinstance(getattr(order, "created_at", None), int) else 0,
            order_id=order.order_id,
            side=getattr(order, "side", "buy"),
            order_type=getattr(order, "order_type", "market"),
            quantity=getattr(order, "quantity", 0),
            price=getattr(order, "price", None),
            status=new_status,
            metadata={"old_status": old_status, "new_status": new_status},
        )
        await self._publish("execution.orders.updated", event.to_dict())
        logger.info(f"Published order_updated: {order.order_id}")

    async def publish_order_filled(self, order: Order, fill_quantity: float, fill_price: float) -> None:
        event = OrderFilled(
            order=order,
            fill_quantity=fill_quantity,
            fill_price=fill_price,
        )
        await self._publish("execution.orders.filled", event.to_dict())
        logger.info(f"Published order_filled: {order.order_id}")

    async def publish_position_updated(self, position, old_quantity: float, new_quantity: float) -> None:
        event = PositionUpdated(
            position=position,
            old_quantity=old_quantity,
            new_quantity=new_quantity,
        )
        await self._publish("execution.positions.updated", event.to_dict())
        logger.info(f"Published position_updated: {position.symbol}")

    async def _publish(self, topic: str, data: Dict[str, Any]) -> None:
        try:
            broker = await self._get_broker()
            if broker:
                await broker.publish(topic, data)
        except Exception as e:
            logger.error(f"Failed to publish to {topic}: {e}")
