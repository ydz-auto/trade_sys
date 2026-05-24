from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Any


class Exchange(str, Enum):
    BINANCE = "binance"
    OKX = "okx"
    COINBASE = "coinbase"
    KRAKEN = "kraken"
    BYBIT = "bybit"


class Timeframe(str, Enum):
    S1 = "1s"
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"

    @property
    def seconds(self) -> int:
        mapping = {
            "1s": 1,
            "1m": 60,
            "5m": 300,
            "15m": 900,
            "30m": 1800,
            "1h": 3600,
            "4h": 14400,
            "1d": 86400,
            "1w": 604800,
        }
        return mapping.get(self.value, 60)

    @classmethod
    def from_string(cls, tf: str) -> "Timeframe":
        return cls(tf)


class CanonicalSymbol(str, Enum):
    BTC = "BTC"
    ETH = "ETH"
    SOL = "SOL"
    BNB = "BNB"
    XRP = "XRP"
    ADA = "ADA"
    AVAX = "AVAX"
    DOGE = "DOGE"
    DOT = "DOT"
    LINK = "LINK"


@dataclass
class Candle:
    symbol: str
    exchange: Exchange
    timeframe: Timeframe
    open_time: int
    close_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float = 0.0
    trade_count: int = 0
    is_closed: bool = True
    source: str = "aggregated"
    event_time: int = field(default_factory=lambda: int(datetime.now().timestamp() * 1000))
    is_complete: bool = True
    missing_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def canonical_symbol(self) -> str:
        return self.symbol.upper().replace("USDT", "").replace("USD", "")

    def get_bucket(self) -> int:
        return self.open_time - (self.open_time % (self.timeframe.seconds * 1000))

    def is_bullish(self) -> bool:
        return self.close > self.open

    def is_bearish(self) -> bool:
        return self.close < self.open

    def get_body(self) -> float:
        return abs(self.close - self.open)

    def get_range(self) -> float:
        return self.high - self.low

    def get_upper_shadow(self) -> float:
        return self.high - max(self.open, self.close)

    def get_lower_shadow(self) -> float:
        return min(self.open, self.close) - self.low

    def to_dict(self) -> Dict:
        return {
            "exchange": self.exchange.value if isinstance(self.exchange, Exchange) else self.exchange,
            "symbol": self.symbol,
            "timeframe": self.timeframe.value if isinstance(self.timeframe, Timeframe) else self.timeframe,
            "open_time": self.open_time,
            "close_time": self.close_time,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "quote_volume": self.quote_volume,
            "trade_count": self.trade_count,
            "is_closed": self.is_closed,
            "source": self.source,
            "event_time": self.event_time,
            "is_complete": self.is_complete,
            "missing_count": self.missing_count,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Candle":
        return cls(
            exchange=data.get("exchange", "binance") if isinstance(data.get("exchange"), str) else Exchange(data.get("exchange", "binance")),
            symbol=data["symbol"],
            timeframe=Timeframe(data["timeframe"]) if isinstance(data["timeframe"], str) else data["timeframe"],
            open_time=data["open_time"],
            close_time=data.get("close_time", data["open_time"] + data.get("timeframe", 60000)),
            open=float(data["open"]),
            high=float(data["high"]),
            low=float(data["low"]),
            close=float(data["close"]),
            volume=float(data["volume"]),
            quote_volume=float(data.get("quote_volume", 0)),
            trade_count=int(data.get("trade_count", 0)),
            is_closed=data.get("is_closed", True),
            source=data.get("source", "aggregated"),
            event_time=data.get("event_time", int(datetime.now().timestamp() * 1000)),
        )


@dataclass
class Trade:
    symbol: str
    exchange: Exchange
    timestamp: int
    price: float
    quantity: float
    quote_quantity: float
    is_buyer_maker: bool
    trade_id: str = ""

    @property
    def side(self) -> str:
        return "sell" if self.is_buyer_maker else "buy"

    @property
    def canonical_symbol(self) -> str:
        return self.symbol.upper().replace("USDT", "").replace("USD", "")

    def to_dict(self) -> Dict:
        return {
            "exchange": self.exchange.value if isinstance(self.exchange, Exchange) else self.exchange,
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
    def from_dict(cls, data: Dict) -> "Trade":
        return cls(
            exchange=data.get("exchange", "binance") if isinstance(data.get("exchange"), str) else Exchange(data.get("exchange", "binance")),
            symbol=data["symbol"],
            trade_id=data.get("trade_id", ""),
            price=float(data["price"]),
            quantity=float(data["quantity"]),
            quote_quantity=float(data.get("quote_quantity", 0)),
            timestamp=int(data["timestamp"]),
            is_buyer_maker=bool(data.get("is_buyer_maker", False)),
        )


@dataclass
class OrderBookLevel:
    price: float
    quantity: float


@dataclass
class OrderBook:
    symbol: str
    exchange: Exchange
    timestamp: int
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]

    def get_mid_price(self) -> float:
        if not self.bids or not self.asks:
            return 0.0
        return (self.bids[0].price + self.asks[0].price) / 2

    def get_spread(self) -> float:
        if not self.bids or not self.asks:
            return 0.0
        return self.asks[0].price - self.bids[0].price

    def get_imbalance(self) -> float:
        if not self.bids or not self.asks:
            return 0.0
        bid_vol = sum(b.quantity for b in self.bids[:10])
        ask_vol = sum(a.quantity for a in self.asks[:10])
        total = bid_vol + ask_vol
        if total == 0:
            return 0.0
        return (bid_vol - ask_vol) / total
