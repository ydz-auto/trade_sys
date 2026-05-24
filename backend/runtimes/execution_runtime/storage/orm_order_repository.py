import uuid
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from domain.execution.models import Order
from domain.models import ExecutionOrder

logger = logging.getLogger(__name__)


class ORMOrderRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, order: Order) -> Order:
        db_order = await self.get_by_order_id(order.order_id)

        if db_order is None:
            db_order = ExecutionOrder(
                id=uuid.uuid4(),
                order_id=order.order_id,
                client_order_id=order.client_order_id,
                exchange_order_id=order.exchange_order_id,
                symbol=order.symbol,
                exchange=order.exchange.value if hasattr(order.exchange, "value") else order.exchange,
                market_type=order.market_type.value if hasattr(order.market_type, "value") else order.market_type,
                side=order.side.value if hasattr(order.side, "value") else order.side,
                order_type=order.order_type.value if hasattr(order.order_type, "value") else order.order_type,
                quantity=order.quantity,
                price=order.price,
                stop_price=order.stop_price,
                status=order.status.value if hasattr(order.status, "value") else order.status,
                filled_quantity=order.filled_quantity or 0,
                avg_fill_price=order.avg_fill_price,
                leverage=order.leverage or 1,
                reduce_only=order.reduce_only or False,
                time_in_force=order.time_in_force.value if hasattr(order.time_in_force, "value") else "GTC",
                error_message=order.error_message,
                extra_data=order.metadata or {},
            )
            self.session.add(db_order)
        else:
            db_order.status = order.status.value if hasattr(order.status, "value") else order.status
            db_order.filled_quantity = order.filled_quantity or 0
            db_order.avg_fill_price = order.avg_fill_price
            db_order.exchange_order_id = order.exchange_order_id
            db_order.error_message = order.error_message
            db_order.extra_data = order.metadata or {}

        await self.session.commit()
        logger.debug(f"Saved order to DB: {order.order_id}")
        return order

    async def get_by_order_id(self, order_id: str) -> Optional[ExecutionOrder]:
        stmt = select(ExecutionOrder).where(ExecutionOrder.order_id == order_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_exchange_order_id(self, exchange_order_id: str, exchange: str) -> Optional[ExecutionOrder]:
        stmt = select(ExecutionOrder).where(
            ExecutionOrder.exchange_order_id == exchange_order_id,
            ExecutionOrder.exchange == exchange,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_symbol(self, symbol: str, exchange: Optional[str] = None, limit: int = 100) -> List[ExecutionOrder]:
        stmt = select(ExecutionOrder).where(ExecutionOrder.symbol == symbol)
        if exchange:
            stmt = stmt.where(ExecutionOrder.exchange == exchange)
        stmt = stmt.order_by(ExecutionOrder.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_status(self, status: str, limit: int = 100) -> List[ExecutionOrder]:
        stmt = select(ExecutionOrder).where(ExecutionOrder.status == status)
        stmt = stmt.order_by(ExecutionOrder.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_recent(self, limit: int = 100) -> List[ExecutionOrder]:
        stmt = select(ExecutionOrder).order_by(ExecutionOrder.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete(self, order_id: str) -> bool:
        stmt = delete(ExecutionOrder).where(ExecutionOrder.order_id == order_id)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0

    async def count_all(self) -> int:
        stmt = select(func.count()).select_from(ExecutionOrder)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    def to_domain_model(self, db_order: ExecutionOrder) -> Order:
        from domain.execution.models import OrderSide, OrderType, OrderStatus, MarketType, Exchange, TimeInForce

        return Order(
            order_id=db_order.order_id,
            client_order_id=db_order.client_order_id,
            exchange_order_id=db_order.exchange_order_id,
            symbol=db_order.symbol,
            exchange=Exchange(db_order.exchange) if db_order.exchange else Exchange.BINANCE,
            market_type=MarketType(db_order.market_type) if db_order.market_type else MarketType.SPOT,
            side=OrderSide(db_order.side) if db_order.side else OrderSide.BUY,
            order_type=OrderType(db_order.order_type) if db_order.order_type else OrderType.MARKET,
            quantity=db_order.quantity,
            price=db_order.price,
            stop_price=db_order.stop_price,
            status=OrderStatus(db_order.status) if db_order.status else OrderStatus.PENDING,
            filled_quantity=db_order.filled_quantity,
            avg_fill_price=db_order.avg_fill_price,
            leverage=db_order.leverage,
            reduce_only=db_order.reduce_only,
            time_in_force=TimeInForce(db_order.time_in_force) if db_order.time_in_force else TimeInForce.GTC,
            error_message=db_order.error_message,
            metadata=db_order.extra_data or {},
            created_at=db_order.created_at,
            updated_at=db_order.updated_at,
        )
