"""
Candle Model - K线数据模型
统一时间真相层
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from enum import Enum

from shared.contracts import Exchange, Timeframe as ContractTimeframe


class Timeframe(str, Enum):
    """时间周期"""
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
        """从字符串创建"""
        return cls(tf)

    def to_contract(self) -> ContractTimeframe:
        """转换为合约 Timeframe"""
        mapping = {
            "1s": ContractTimeframe.M1,
            "1m": ContractTimeframe.M1,
            "5m": ContractTimeframe.M5,
            "15m": ContractTimeframe.M15,
            "30m": ContractTimeframe.M30,
            "1h": ContractTimeframe.H1,
            "4h": ContractTimeframe.H4,
            "1d": ContractTimeframe.D1,
            "1w": ContractTimeframe.W1,
        }
        return mapping.get(self.value, ContractTimeframe.M1)


@dataclass
class Candle:
    """K线数据 - 系统唯一标准"""
    exchange: str
    symbol: str
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
        """获取时间桶（用于窗口对齐）"""
        return self.open_time - (self.open_time % self.timeframe.seconds * 1000)

    def is_bullish(self) -> bool:
        """是否阳线"""
        return self.close > self.open

    def is_bearish(self) -> bool:
        """是否阴线"""
        return self.close < self.open

    def get_body(self) -> float:
        """获取实体大小"""
        return abs(self.close - self.open)

    def get_range(self) -> float:
        """获取波动范围"""
        return self.high - self.low

    def get_upper_shadow(self) -> float:
        """获取上影线"""
        return self.high - max(self.open, self.close)

    def get_lower_shadow(self) -> float:
        """获取下影线"""
        return min(self.open, self.close) - self.low

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exchange": self.exchange,
            "symbol": self.symbol,
            "timeframe": self.timeframe.value,
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

    def to_clickhouse_row(self) -> Dict[str, Any]:
        """ClickHouse 格式"""
        return {
            "exchange": self.exchange,
            "symbol": self.symbol,
            "timeframe": self.timeframe.value,
            "open_time": self.open_time,
            "open_time_dt": datetime.fromtimestamp(self.open_time / 1000),
            "close_time": self.close_time,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "quote_volume": self.quote_volume,
            "trade_count": self.trade_count,
            "is_closed": 1 if self.is_closed else 0,
            "is_complete": 1 if self.is_complete else 0,
            "missing_count": self.missing_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Candle":
        """从字典创建"""
        return cls(
            exchange=data["exchange"],
            symbol=data["symbol"],
            timeframe=Timeframe(data["timeframe"]),
            open_time=data["open_time"],
            close_time=data["close_time"],
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
class CandleWindow:
    """K线窗口状态（用于内存聚合）"""
    exchange: str
    symbol: str
    timeframe: Timeframe

    bucket: int

    open: float = 0.0
    high: float = float("-inf")
    low: float = float("inf")
    close: float = 0.0

    volume: float = 0.0
    quote_volume: float = 0.0
    trade_count: int = 0

    first_trade_time: int = 0
    last_trade_time: int = 0

    is_closed: bool = False
    trades: list = field(default_factory=list)

    def update(self, price: float, quantity: float, quote: float, trade_time: int):
        """更新窗口"""
        if self.first_trade_time == 0:
            self.first_trade_time = trade_time
            self.open = price
            self.high = price
            self.low = price

        self.last_trade_time = trade_time
        self.close = price

        self.high = max(self.high, price)
        self.low = min(self.low, price)

        self.volume += quantity
        self.quote_volume += quote
        self.trade_count += 1

    def to_candle(self, open_time: int, close_time: int) -> Candle:
        """转换为 Candle"""
        return Candle(
            exchange=self.exchange,
            symbol=self.symbol,
            timeframe=self.timeframe,
            open_time=open_time,
            close_time=close_time,
            open=self.open,
            high=self.high if self.high != float("-inf") else self.open,
            low=self.low if self.low != float("inf") else self.open,
            close=self.close,
            volume=self.volume,
            quote_volume=self.quote_volume,
            trade_count=self.trade_count,
            is_closed=True,
            source="aggregated",
            event_time=int(datetime.now().timestamp() * 1000),
        )

    def reset(self):
        """重置窗口"""
        self.open = 0.0
        self.high = float("-inf")
        self.low = float("inf")
        self.close = 0.0
        self.volume = 0.0
        self.quote_volume = 0.0
        self.trade_count = 0
        self.first_trade_time = 0
        self.last_trade_time = 0
        self.is_closed = False
        self.trades = []
