"""
Aggregation Service - K线聚合服务
负责将低周期K线聚合为高周期K线

数据流：
raw.trade.* → trade_to_1s → kline.1s
raw.kline.1m.closed → aggregation → kline.5m/15m/1h/4h/1d

核心职责：
- 1m → 5m/15m/1h (直接从 closed 1m 生成)
- trade → 1s candle
- orderbook snapshot feature
- 时间对齐
- 缺失检测
- replay rebuild
"""

from .models.candle_model import Candle, Timeframe, CandleWindow
from .models.trade_model import Trade, TradeBatch
from .models.orderbook_model import OrderBookSnapshot, OrderBookFeature
from .service import AggregationService, get_aggregation_service

__all__ = [
    "Candle",
    "Timeframe",
    "CandleWindow",
    "Trade",
    "TradeBatch",
    "OrderBookSnapshot",
    "OrderBookFeature",
    "AggregationService",
    "get_aggregation_service",
]
