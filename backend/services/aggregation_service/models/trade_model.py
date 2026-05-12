"""
Trade Model - 成交数据模型
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any

from shared.contracts import Exchange


@dataclass
class Trade:
    """成交数据"""
    exchange: str
    symbol: str
    trade_id: str
    price: float
    quantity: float
    quote_quantity: float
    timestamp: int
    is_buyer_maker: bool

    @property
    def side(self) -> str:
        return "sell" if self.is_buyer_maker else "buy"

    @property
    def canonical_symbol(self) -> str:
        return self.symbol.upper().replace("USDT", "").replace("USD", "")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exchange": self.exchange,
            "symbol": self.symbol,
            "trade_id": self.trade_id,
            "price": self.price,
            "quantity": self.quantity,
            "quote_quantity": self.quote_quantity,
            "timestamp": self.timestamp,
            "is_buyer_maker": self.is_buyer_maker,
            "side": self.side,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Trade":
        return cls(
            exchange=data["exchange"],
            symbol=data["symbol"],
            trade_id=data.get("trade_id", ""),
            price=float(data["price"]),
            quantity=float(data["quantity"]),
            quote_quantity=float(data.get("quote_quantity", 0)),
            timestamp=int(data["timestamp"]),
            is_buyer_maker=bool(data.get("is_buyer_maker", False)),
        )


@dataclass
class TradeBatch:
    """成交批次（用于批量处理）"""
    exchange: str
    symbol: str
    trades: List[Trade]
    start_time: int
    end_time: int

    def get_volume(self) -> float:
        return sum(t.quantity for t in self.trades)

    def get_quote_volume(self) -> float:
        return sum(t.quote_quantity for t in self.trades)

    def get_trade_count(self) -> int:
        return len(self.trades)

    def get_buy_volume(self) -> float:
        return sum(t.quantity for t in self.trades if not t.is_buyer_maker)

    def get_sell_volume(self) -> float:
        return sum(t.quantity for t in self.trades if t.is_buyer_maker)

    def get_vwap(self) -> float:
        total_quote = self.get_quote_volume()
        total_qty = self.get_volume()
        if total_qty == 0:
            return 0.0
        return total_quote / total_qty

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exchange": self.exchange,
            "symbol": self.symbol,
            "trades": [t.to_dict() for t in self.trades],
            "start_time": self.start_time,
            "end_time": self.end_time,
        }
