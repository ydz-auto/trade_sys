from typing import Dict, List, Optional
from datetime import datetime

from domain.execution.models import (
    Order,
    Position,
    OrderSide,
    Exchange,
    MarketType,
)
from infrastructure.logging import get_logger

logger = get_logger("execution_service.position_manager")


class PositionManager:

    def __init__(self):
        self._positions: Dict[str, Position] = {}

    def _make_key(self, symbol: str, exchange: Exchange, market_type: MarketType) -> str:
        return f"{exchange.value}:{market_type.value}:{symbol}"

    def update_position(self, order: Order, fill_price: float, fill_quantity: float) -> Position:
        key = self._make_key(order.symbol, order.exchange, order.market_type)

        if key not in self._positions:
            self._positions[key] = Position(
                symbol=order.symbol,
                exchange=order.exchange,
                quantity=0,
                average_price=0,
                market_type=order.market_type,
                entry_time=datetime.now(),
            )

        position = self._positions[key]
        old_quantity = position.quantity

        if order.side == OrderSide.BUY:
            if position.quantity >= 0:
                total_cost = position.quantity * position.average_price + fill_quantity * fill_price
                position.quantity += fill_quantity
                position.average_price = total_cost / position.quantity if position.quantity > 0 else 0
            else:
                position.quantity += fill_quantity
                if position.quantity > 0:
                    position.average_price = fill_price
                    position.entry_time = datetime.now()
                elif position.quantity == 0:
                    position.average_price = 0
                    position.entry_time = None
        else:
            if position.quantity <= 0:
                total_cost = abs(position.quantity) * position.average_price + fill_quantity * fill_price
                position.quantity -= fill_quantity
                position.average_price = total_cost / abs(position.quantity) if position.quantity < 0 else 0
            else:
                position.quantity -= fill_quantity
                if position.quantity < 0:
                    position.average_price = fill_price
                    position.entry_time = datetime.now()
                elif position.quantity == 0:
                    position.average_price = 0
                    position.entry_time = None

        position.updated_at = datetime.now()

        logger.info(
            f"Position updated: {order.symbol} {old_quantity} -> {position.quantity} @ {position.average_price}"
        )

        return position

    def get_position(self, symbol: str, exchange: Exchange, market_type: MarketType = MarketType.SPOT) -> Optional[Position]:
        key = self._make_key(symbol, exchange, market_type)
        return self._positions.get(key)

    def get_all_positions(self) -> List[Position]:
        return [p for p in self._positions.values() if abs(p.quantity) > 1e-8]

    def get_positions_by_exchange(self, exchange: Exchange) -> List[Position]:
        return [
            p for p in self._positions.values()
            if p.exchange == exchange and abs(p.quantity) > 1e-8
        ]

    def close_position(self, symbol: str, exchange: Exchange, market_type: MarketType = MarketType.SPOT) -> bool:
        key = self._make_key(symbol, exchange, market_type)
        if key in self._positions:
            position = self._positions[key]
            position.quantity = 0
            position.average_price = 0
            position.unrealized_pnl = 0
            position.updated_at = datetime.now()
            position.entry_time = None
            logger.info(f"Position closed: {symbol}")
            return True
        return False

    def update_position_price(self, symbol: str, exchange: Exchange, current_price: float, market_type: MarketType = MarketType.SPOT) -> Optional[Position]:
        key = self._make_key(symbol, exchange, market_type)
        if key in self._positions:
            position = self._positions[key]
            position.current_price = current_price
            if position.quantity != 0:
                position.unrealized_pnl = (current_price - position.average_price) * position.quantity
            position.updated_at = datetime.now()
            return position
        return None

    def get_total_unrealized_pnl(self) -> float:
        return sum(p.unrealized_pnl for p in self._positions.values())

    def get_total_position_value(self) -> float:
        return sum(
            abs(p.quantity) * p.current_price
            for p in self._positions.values()
            if p.current_price > 0
        )

    def has_position(self, symbol: str, exchange: Exchange, market_type: MarketType = MarketType.SPOT) -> bool:
        position = self.get_position(symbol, exchange, market_type)
        return position is not None and abs(position.quantity) > 1e-8

    def get_position_count(self) -> int:
        return len([p for p in self._positions.values() if abs(p.quantity) > 1e-8])
