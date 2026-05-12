"""
OrderBook Model - 订单簿数据模型
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any

from shared.contracts import Exchange


@dataclass
class OrderBookLevel:
    """订单簿级别"""
    price: float
    quantity: float


@dataclass
class OrderBookSnapshot:
    """订单簿快照"""
    exchange: str
    symbol: str
    timestamp: int

    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]

    last_update_id: int = 0

    def get_mid_price(self) -> float:
        if not self.bids or not self.asks:
            return 0.0
        return (self.bids[0].price + self.asks[0].price) / 2

    def get_spread(self) -> float:
        if not self.bids or not self.asks:
            return 0.0
        return self.asks[0].price - self.bids[0].price

    def get_bid_volume(self, depth: int = 10) -> float:
        return sum(b.quantity for b in self.bids[:depth])

    def get_ask_volume(self, depth: int = 10) -> float:
        return sum(a.quantity for a in self.asks[:depth])

    def get_imbalance(self, depth: int = 10) -> float:
        bid_vol = self.get_bid_volume(depth)
        ask_vol = self.get_ask_volume(depth)
        total = bid_vol + ask_vol
        if total == 0:
            return 0.0
        return (bid_vol - ask_vol) / total

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exchange": self.exchange,
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "bids": [(b.price, b.quantity) for b in self.bids],
            "asks": [(a.price, a.quantity) for a in self.asks],
            "last_update_id": self.last_update_id,
        }


@dataclass
class OrderBookFeature:
    """订单簿特征（聚合服务输出）"""
    exchange: str
    symbol: str
    timestamp: int

    spread: float
    mid_price: float
    imbalance: float

    bid_vol_5: float
    ask_vol_5: float
    bid_vol_10: float
    ask_vol_10: float

    weighted_bid_price: float
    weighted_ask_price: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exchange": self.exchange,
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "spread": self.spread,
            "mid_price": self.mid_price,
            "imbalance": self.imbalance,
            "bid_vol_5": self.bid_vol_5,
            "ask_vol_5": self.ask_vol_5,
            "bid_vol_10": self.bid_vol_10,
            "ask_vol_10": self.ask_vol_10,
            "weighted_bid_price": self.weighted_bid_price,
            "weighted_ask_price": self.weighted_ask_price,
        }

    @classmethod
    def from_snapshot(cls, snapshot: OrderBookSnapshot) -> "OrderBookFeature":
        """从快照计算特征"""
        bid_vol_5 = sum(b.quantity for b in snapshot.bids[:5])
        ask_vol_5 = sum(a.quantity for a in snapshot.asks[:5])
        bid_vol_10 = sum(b.quantity for b in snapshot.bids[:10])
        ask_vol_10 = sum(a.quantity for a in snapshot.asks[:10])

        weighted_bid = sum(b.price * b.quantity for b in snapshot.bids[:10])
        weighted_ask = sum(a.price * a.quantity for a in snapshot.asks[:10])

        bid_total = sum(b.quantity for b in snapshot.bids[:10])
        ask_total = sum(a.quantity for a in snapshot.asks[:10])

        return cls(
            exchange=snapshot.exchange,
            symbol=snapshot.symbol,
            timestamp=snapshot.timestamp,
            spread=snapshot.get_spread(),
            mid_price=snapshot.get_mid_price(),
            imbalance=snapshot.get_imbalance(10),
            bid_vol_5=bid_vol_5,
            ask_vol_5=ask_vol_5,
            bid_vol_10=bid_vol_10,
            ask_vol_10=ask_vol_10,
            weighted_bid_price=weighted_bid / bid_total if bid_total > 0 else 0,
            weighted_ask_price=weighted_ask / ask_total if ask_total > 0 else 0,
        )
