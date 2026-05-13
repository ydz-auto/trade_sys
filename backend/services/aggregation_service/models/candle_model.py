"""
Candle Model - K线数据模型
统一从 shared.contracts 导入，aggregation_service 是真相层
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List
from enum import Enum

from shared.contracts import Exchange, Timeframe, Candle as ContractCandle


class Candle(ContractCandle):
    """K线数据 - 继承自 contracts，作为真相层的标准"""
    pass


@dataclass
class CandleWindow:
    """K线窗口状态（用于内存聚合）"""
    exchange: Exchange
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
