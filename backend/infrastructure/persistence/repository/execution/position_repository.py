from typing import Dict, List, Optional

from domain.execution.models import Position, Exchange, MarketType
from domain.execution.position_reader import PositionReader
from infrastructure.persistence.state.types import StateType
from infrastructure.persistence.state.manager import StateManager, get_state_manager
from infrastructure.logging import get_logger

logger = get_logger("infrastructure.persistence.repository.execution.position")


class PositionRepository(PositionReader):

    def __init__(self, state_manager: StateManager = None):
        self._state_manager = state_manager or get_state_manager()

    def _make_key(self, symbol: str, exchange: Exchange, market_type: MarketType) -> str:
        return f"{exchange.value}:{market_type.value}:{symbol}"

    async def save(self, position: Position) -> None:
        key = self._make_key(position.symbol, position.exchange, position.market_type)
        self._state_manager.set_state(
            StateType.POSITION,
            position.to_dict(),
            key=key,
            persist=True,
        )
        logger.debug(f"Position saved: {position.symbol}")

    async def get(self, symbol: str, exchange: Exchange, market_type: MarketType = MarketType.SPOT) -> Optional[Position]:
        key = self._make_key(symbol, exchange, market_type)
        data = self._state_manager.get_state(StateType.POSITION, key=key)
        if data:
            return Position.from_dict(data)
        return None

    async def get_all(self) -> List[Position]:
        data = self._state_manager.get_state(StateType.POSITION) or {}
        return [
            Position.from_dict(p)
            for p in data.values()
            if isinstance(p, dict) and abs(p.get("quantity", 0)) > 1e-8
        ]

    async def get_by_exchange(self, exchange: Exchange) -> List[Position]:
        positions = await self.get_all()
        return [p for p in positions if p.exchange == exchange]

    async def delete(self, symbol: str, exchange: Exchange, market_type: MarketType = MarketType.SPOT) -> None:
        key = self._make_key(symbol, exchange, market_type)
        self._state_manager.delete_state(StateType.POSITION, key=key)
        logger.debug(f"Position deleted: {symbol}")

    async def update(
        self,
        symbol: str,
        exchange: Exchange,
        updates: Dict,
        market_type: MarketType = MarketType.SPOT,
    ) -> Optional[Position]:
        position = await self.get(symbol, exchange, market_type)
        if position:
            for key, value in updates.items():
                if hasattr(position, key):
                    setattr(position, key, value)
            await self.save(position)
            return position
        return None

    async def close(self, symbol: str, exchange: Exchange, market_type: MarketType = MarketType.SPOT) -> None:
        await self.delete(symbol, exchange, market_type)
        logger.info(f"Position closed: {symbol}")

    async def get_total_unrealized_pnl(self) -> float:
        positions = await self.get_all()
        return sum(p.unrealized_pnl for p in positions)

    async def get_total_position_value(self) -> float:
        positions = await self.get_all()
        return sum(
            abs(p.quantity) * p.current_price
            for p in positions
            if p.current_price > 0
        )

    async def has_position(self, symbol: str, exchange: Exchange, market_type: MarketType = MarketType.SPOT) -> bool:
        position = await self.get(symbol, exchange, market_type)
        return position is not None and abs(position.quantity) > 1e-8

    async def get_position_count(self) -> int:
        positions = await self.get_all()
        return len(positions)
