import uuid
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from domain.execution.models import Position
from domain.models import ExecutionPosition

logger = logging.getLogger(__name__)


class ORMPositionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, position: Position) -> Position:
        db_position = await self.get(
            position.symbol,
            position.exchange.value if hasattr(position.exchange, "value") else position.exchange,
            position.market_type.value if hasattr(position.market_type, "value") else position.market_type,
        )

        if db_position is None:
            position_id = f"{position.symbol}_{position.exchange.value if hasattr(position.exchange, 'value') else position.exchange}_{position.market_type.value if hasattr(position.market_type, 'value') else position.market_type}"
            db_position = ExecutionPosition(
                id=uuid.uuid4(),
                position_id=position_id,
                symbol=position.symbol,
                exchange=position.exchange.value if hasattr(position.exchange, "value") else position.exchange,
                market_type=position.market_type.value if hasattr(position.market_type, "value") else position.market_type,
                quantity=position.quantity or 0,
                avg_entry_price=position.average_price or 0,
                current_price=position.current_price or 0,
                unrealized_pnl=position.unrealized_pnl or 0,
                realized_pnl=position.realized_pnl or 0,
                leverage=position.leverage or 1,
                margin=position.margin or 0,
                liquidation_price=position.liquidation_price,
                extra_data={},
            )
            self.session.add(db_position)
        else:
            db_position.quantity = position.quantity or 0
            db_position.avg_entry_price = position.average_price or 0
            db_position.current_price = position.current_price or 0
            db_position.unrealized_pnl = position.unrealized_pnl or 0
            db_position.realized_pnl = position.realized_pnl or 0
            db_position.leverage = position.leverage or 1
            db_position.margin = position.margin or 0
            db_position.liquidation_price = position.liquidation_price
            db_position.extra_data = {}

        await self.session.commit()
        logger.debug(f"Saved position to DB: {position.symbol}")
        return position

    async def get(
        self,
        symbol: str,
        exchange: str,
        market_type: str = "spot",
    ) -> Optional[ExecutionPosition]:
        stmt = select(ExecutionPosition).where(
            and_(
                ExecutionPosition.symbol == symbol,
                ExecutionPosition.exchange == exchange,
                ExecutionPosition.market_type == market_type,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self, exchange: Optional[str] = None) -> List[ExecutionPosition]:
        stmt = select(ExecutionPosition)
        if exchange:
            stmt = stmt.where(ExecutionPosition.exchange == exchange)
        stmt = stmt.order_by(ExecutionPosition.updated_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_active(self, exchange: Optional[str] = None) -> List[ExecutionPosition]:
        stmt = select(ExecutionPosition).where(ExecutionPosition.quantity != 0)
        if exchange:
            stmt = stmt.where(ExecutionPosition.exchange == exchange)
        stmt = stmt.order_by(ExecutionPosition.updated_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete(self, symbol: str, exchange: str, market_type: str = "spot") -> bool:
        stmt = select(ExecutionPosition).where(
            and_(
                ExecutionPosition.symbol == symbol,
                ExecutionPosition.exchange == exchange,
                ExecutionPosition.market_type == market_type,
            )
        )
        result = await self.session.execute(stmt)
        db_position = result.scalar_one_or_none()
        if db_position:
            db_position.quantity = 0
            await self.session.commit()
            return True
        return False

    def to_domain_model(self, db_position: ExecutionPosition) -> Position:
        from domain.execution.models import Exchange, MarketType

        return Position(
            symbol=db_position.symbol,
            exchange=Exchange(db_position.exchange) if db_position.exchange else Exchange.BINANCE,
            market_type=MarketType(db_position.market_type) if db_position.market_type else MarketType.SPOT,
            quantity=db_position.quantity,
            average_price=db_position.avg_entry_price,
            current_price=db_position.current_price,
            unrealized_pnl=db_position.unrealized_pnl,
            realized_pnl=db_position.realized_pnl,
            leverage=db_position.leverage,
            margin=db_position.margin,
            liquidation_price=db_position.liquidation_price,
            entry_time=None,
            updated_at=db_position.updated_at or datetime.now(),
        )
