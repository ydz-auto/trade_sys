import uuid
from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime

from .exposure import Position, PositionSide, PositionStatus


class PortfolioState(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    LIQUIDATING = "liquidating"
    CLOSED = "closed"


@dataclass
class PortfolioMetrics:
    total_value: float = 0.0
    total_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    total_margin: float = 0.0
    available_margin: float = 0.0
    margin_usage: float = 0.0
    position_count: int = 0
    long_count: int = 0
    short_count: int = 0
    exposure_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    sharpe_ratio: float = 0.0


@dataclass
class Portfolio:
    portfolio_id: str = field(default_factory=lambda: f"pf_{uuid.uuid4().hex[:12]}")
    name: str = "default"

    state: PortfolioState = PortfolioState.ACTIVE

    initial_capital: float = 10000.0
    current_capital: float = 10000.0
    available_capital: float = 10000.0

    positions: Dict[str, Position] = field(default_factory=dict)

    base_currency: str = "USDT"

    max_position_size: float = 0.2
    max_total_exposure: float = 1.0
    max_drawdown: float = 0.2

    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    _trade_count: int = field(default=0, repr=False)
    _win_count: int = field(default=0, repr=False)
    _pnl_history: List[float] = field(default_factory=list, repr=False)

    def get_position(self, symbol: str, exchange: str = "binance") -> Optional[Position]:
        key = f"{exchange}:{symbol}"
        return self.positions.get(key)

    def get_or_create_position(self, symbol: str, exchange: str = "binance", strategy_id: str = "") -> Position:
        key = f"{exchange}:{symbol}"

        if key not in self.positions:
            position = Position(
                position_id=f"pos_{uuid.uuid4().hex[:12]}",
                symbol=symbol,
                exchange=exchange,
                strategy_id=strategy_id,
            )
            self.positions[key] = position

        return self.positions[key]

    def add_position(self, position: Position) -> None:
        key = f"{position.exchange}:{position.symbol}"
        self.positions[key] = position
        self.updated_at = datetime.utcnow()

    def remove_position(self, symbol: str, exchange: str = "binance") -> Optional[Position]:
        key = f"{exchange}:{symbol}"
        position = self.positions.pop(key, None)
        self.updated_at = datetime.utcnow()
        return position

    def update_position_price(self, symbol: str, current_price: float, exchange: str = "binance") -> None:
        position = self.get_position(symbol, exchange)
        if position:
            position.update_price(current_price)
            self.updated_at = datetime.utcnow()

    def update_all_prices(self, prices: Dict[str, float]) -> None:
        for key, position in self.positions.items():
            symbol_key = position.symbol
            if symbol_key in prices:
                position.update_price(prices[symbol_key])

        self.updated_at = datetime.utcnow()

    def open_position(
        self,
        symbol: str,
        exchange: str,
        quantity: float,
        price: float,
        leverage: int = 1,
        strategy_id: str = "",
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> Position:
        position = self.get_or_create_position(symbol, exchange, strategy_id)

        position.add_quantity(quantity, price)
        position.leverage = leverage
        position.strategy_id = strategy_id

        if stop_loss:
            position.set_stop_loss(stop_loss)
        if take_profit:
            position.set_take_profit(take_profit)

        margin_used = abs(quantity) * price / leverage
        self.available_capital -= margin_used

        self.updated_at = datetime.utcnow()
        return position

    def close_position(
        self,
        symbol: str,
        exchange: str,
        quantity: Optional[float] = None,
        price: float = 0.0,
    ) -> float:
        position = self.get_position(symbol, exchange)
        if not position or position.is_flat:
            return 0.0

        close_qty = quantity if quantity else abs(position.quantity)
        realized = position.reduce_quantity(close_qty, price)

        self.current_capital += realized
        self.available_capital += position.margin_used

        self._trade_count += 1
        if realized > 0:
            self._win_count += 1

        self._pnl_history.append(realized)

        if position.is_flat:
            self.remove_position(symbol, exchange)

        self.updated_at = datetime.utcnow()
        return realized

    @property
    def total_pnl(self) -> float:
        return self.unrealized_pnl + self.realized_pnl

    @property
    def unrealized_pnl(self) -> float:
        return sum(p.unrealized_pnl for p in self.positions.values())

    @property
    def realized_pnl(self) -> float:
        return sum(p.realized_pnl for p in self.positions.values())

    @property
    def total_value(self) -> float:
        return self.current_capital + self.unrealized_pnl

    @property
    def equity(self) -> float:
        return self.total_value

    @property
    def total_margin(self) -> float:
        return sum(p.margin_used for p in self.positions.values())

    @property
    def margin_usage(self) -> float:
        if self.current_capital > 0:
            return self.total_margin / self.current_capital
        return 0.0

    @property
    def position_count(self) -> int:
        return len([p for p in self.positions.values() if not p.is_flat])

    @property
    def exposure_ratio(self) -> float:
        total_notional = sum(p.notional_value for p in self.positions.values())
        if self.current_capital > 0:
            return total_notional / self.current_capital
        return 0.0

    @property
    def win_rate(self) -> float:
        if self._trade_count > 0:
            return self._win_count / self._trade_count
        return 0.0

    @property
    def pnl_percent(self) -> float:
        if self.initial_capital > 0:
            return (self.total_value - self.initial_capital) / self.initial_capital * 100
        return 0.0

    def get_metrics(self) -> PortfolioMetrics:
        long_count = len([p for p in self.positions.values() if p.is_long])
        short_count = len([p for p in self.positions.values() if p.is_short])

        return PortfolioMetrics(
            total_value=self.total_value,
            total_pnl=self.total_pnl,
            unrealized_pnl=self.unrealized_pnl,
            realized_pnl=self.realized_pnl,
            total_margin=self.total_margin,
            available_margin=self.available_capital,
            margin_usage=self.margin_usage,
            position_count=self.position_count,
            long_count=long_count,
            short_count=short_count,
            exposure_ratio=self.exposure_ratio,
            win_rate=self.win_rate,
        )

    def get_positions_by_strategy(self, strategy_id: str) -> List[Position]:
        return [p for p in self.positions.values() if p.strategy_id == strategy_id]

    def get_positions_by_exchange(self, exchange: str) -> List[Position]:
        return [p for p in self.positions.values() if p.exchange == exchange]

    def get_long_positions(self) -> List[Position]:
        return [p for p in self.positions.values() if p.is_long]

    def get_short_positions(self) -> List[Position]:
        return [p for p in self.positions.values() if p.is_short]

    def can_open_position(self, symbol: str, quantity: float, price: float, leverage: int = 1) -> bool:
        margin_needed = abs(quantity) * price / leverage

        if margin_needed > self.available_capital:
            return False

        notional = abs(quantity) * price
        if notional > self.current_capital * self.max_position_size:
            return False

        new_exposure = self.exposure_ratio + notional / self.current_capital
        if new_exposure > self.max_total_exposure:
            return False

        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "portfolio_id": self.portfolio_id,
            "name": self.name,
            "state": self.state.value,
            "initial_capital": self.initial_capital,
            "current_capital": self.current_capital,
            "available_capital": self.available_capital,
            "total_value": self.total_value,
            "total_pnl": self.total_pnl,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "total_margin": self.total_margin,
            "margin_usage": self.margin_usage,
            "position_count": self.position_count,
            "exposure_ratio": self.exposure_ratio,
            "win_rate": self.win_rate,
            "pnl_percent": self.pnl_percent,
            "positions": {k: p.to_dict() for k, p in self.positions.items()},
            "base_currency": self.base_currency,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Portfolio":
        portfolio = cls(
            portfolio_id=data["portfolio_id"],
            name=data.get("name", "default"),
            state=PortfolioState(data.get("state", "active")),
            initial_capital=data.get("initial_capital", 10000.0),
            current_capital=data.get("current_capital", 10000.0),
            available_capital=data.get("available_capital", 10000.0),
            base_currency=data.get("base_currency", "USDT"),
            max_position_size=data.get("max_position_size", 0.2),
            max_total_exposure=data.get("max_total_exposure", 1.0),
            max_drawdown=data.get("max_drawdown", 0.2),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.utcnow(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.utcnow(),
        )

        for key, pos_data in data.get("positions", {}).items():
            portfolio.positions[key] = Position.from_dict(pos_data)

        return portfolio
