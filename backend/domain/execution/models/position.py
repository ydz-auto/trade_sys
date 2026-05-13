"""
Position Model

持仓模型
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from domain.execution.models.enums import Exchange, MarketType


@dataclass
class Position:
    """持仓"""
    symbol: str
    exchange: Exchange
    quantity: float
    average_price: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    updated_at: datetime = field(default_factory=datetime.now)

    market_type: MarketType = MarketType.SPOT
    leverage: int = 1
    margin: float = 0.0
    liquidation_price: float = 0.0
    entry_time: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "exchange": self.exchange.value,
            "quantity": self.quantity,
            "average_price": self.average_price,
            "current_price": self.current_price,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "updated_at": self.updated_at.isoformat(),
            "market_type": self.market_type.value,
            "leverage": self.leverage,
            "margin": self.margin,
            "liquidation_price": self.liquidation_price,
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Position":
        return cls(
            symbol=data["symbol"],
            exchange=Exchange(data["exchange"]),
            quantity=data["quantity"],
            average_price=data["average_price"],
            current_price=data.get("current_price", 0.0),
            unrealized_pnl=data.get("unrealized_pnl", 0.0),
            realized_pnl=data.get("realized_pnl", 0.0),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.now(),
            market_type=MarketType(data.get("market_type", "spot")),
            leverage=data.get("leverage", 1),
            margin=data.get("margin", 0.0),
            liquidation_price=data.get("liquidation_price", 0.0),
            entry_time=datetime.fromisoformat(data["entry_time"]) if data.get("entry_time") else None,
        )

    def update_price(self, current_price: float) -> None:
        """更新当前价格和未实现盈亏"""
        self.current_price = current_price
        if self.quantity != 0:
            self.unrealized_pnl = (current_price - self.average_price) * self.quantity
        self.updated_at = datetime.now()

    def is_long(self) -> bool:
        """是否多头"""
        return self.quantity > 0

    def is_short(self) -> bool:
        """是否空头"""
        return self.quantity < 0

    def is_flat(self) -> bool:
        """是否无持仓"""
        return abs(self.quantity) < 1e-8
