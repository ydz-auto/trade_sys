"""
Trade to Candle Aggregator - 成交转K线聚合器
将原始成交聚合为1秒K线
"""

from typing import Dict, Optional, Tuple
from datetime import datetime

from infrastructure.logging import get_logger
from services.aggregation_service.models.candle_model import Candle, CandleWindow, Timeframe
from services.aggregation_service.models.trade_model import Trade

logger = get_logger("aggregation_service.trade_aggregator")


class TradeToCandleAggregator:
    """成交转K线聚合器

    将 raw.trade.* 聚合为 kline.*.1s
    """

    def __init__(self):
        self.windows: Dict[Tuple[str, str], CandleWindow] = {}

    def get_window(self, exchange: str, symbol: str) -> CandleWindow:
        """获取或创建窗口"""
        key = (exchange, symbol)
        if key not in self.windows:
            self.windows[key] = CandleWindow(
                exchange=exchange,
                symbol=symbol,
                timeframe=Timeframe.S1,
                bucket=0,
            )
        return self.windows[key]

    def process_trade(self, trade: Trade) -> Optional[Candle]:
        """处理一笔成交，返回1秒K线"""
        window = self.get_window(trade.exchange, trade.symbol)

        bucket_size = 1000
        trade_bucket = (trade.timestamp // bucket_size) * bucket_size

        if window.bucket == 0:
            window.bucket = trade_bucket
            window.open = trade.price
            window.high = trade.price
            window.low = trade.price
            window.close = trade.price
            window.volume = trade.quantity
            window.quote_volume = trade.quote_quantity
            window.trade_count = 1
            window.trades = [trade]
            return None

        if trade_bucket < window.bucket:
            logger.warning(f"Out of order trade: {trade.timestamp} < {window.bucket}")
            return None

        if trade_bucket > window.bucket:
            closed_candle = self._close_window(window)
            window.reset()
            window.bucket = trade_bucket
            window.open = trade.price
            window.high = trade.price
            window.low = trade.price
            window.close = trade.price
            window.volume = trade.quantity
            window.quote_volume = trade.quote_quantity
            window.trade_count = 1
            window.trades = [trade]
            return closed_candle

        window.high = max(window.high, trade.price)
        window.low = min(window.low, trade.price)
        window.close = trade.price
        window.volume += trade.quantity
        window.quote_volume += trade.quote_quantity
        window.trade_count += 1
        window.trades.append(trade)
        return None

    def process_trade_batch(self, trades: list[Trade]) -> list[Candle]:
        """批量处理成交"""
        closed_candles = []
        for trade in trades:
            candle = self.process_trade(trade)
            if candle:
                closed_candles.append(candle)
        return closed_candles

    def _close_window(self, window: CandleWindow) -> Candle:
        """关闭并返回窗口"""
        return Candle(
            exchange=window.exchange,
            symbol=window.symbol,
            timeframe=Timeframe.S1,
            open_time=window.bucket,
            close_time=window.bucket + 999,
            open=window.open,
            high=window.high,
            low=window.low,
            close=window.close,
            volume=window.volume,
            quote_volume=window.quote_volume,
            trade_count=window.trade_count,
            is_closed=True,
            source="aggregated",
            event_time=int(datetime.now().timestamp() * 1000),
        )

    def close_all(self) -> list[Candle]:
        """关闭所有窗口"""
        closed = []
        for key, window in self.windows.items():
            if window.bucket > 0:
                candle = self._close_window(window)
                closed.append(candle)
                window.reset()
        return closed


_aggregator: Optional[TradeToCandleAggregator] = None


def get_trade_aggregator() -> TradeToCandleAggregator:
    """获取全局成交聚合器"""
    global _aggregator
    if _aggregator is None:
        _aggregator = TradeToCandleAggregator()
    return _aggregator
