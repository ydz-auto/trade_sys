"""
Candle Aggregator - K线聚合器
将低周期K线聚合为高周期K线
"""

from typing import Dict, Optional, Tuple
from datetime import datetime

from infrastructure.logging import get_logger
from shared.contracts import Exchange, Timeframe
from ..models.candle_model import Candle, CandleWindow

logger = get_logger("aggregation_service.candle_aggregator")


class CandleAggregator:
    """K线聚合器

    核心逻辑：
    - 1m → 5m/15m/1h (直接从 closed 1m 生成)
    - 所有高周期直接从 1m 生成，不链式聚合
    """

    def __init__(self):
        self.windows: Dict[Tuple[str, str, Timeframe], CandleWindow] = {}

    def get_window(self, exchange: Exchange, symbol: str, timeframe: Timeframe) -> CandleWindow:
        """获取或创建窗口"""
        key = (exchange.value if isinstance(exchange, Exchange) else exchange, symbol, timeframe)
        if key not in self.windows:
            if isinstance(exchange, str):
                exchange = Exchange(exchange)
            self.windows[key] = CandleWindow(
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
                bucket=0,
            )
        return self.windows[key]

    def process_candle(self, candle: Candle) -> Optional[Candle]:
        """处理一根K线，返回聚合后的K线"""
        if not candle.is_closed:
            return None

        result = []
        target_timeframes = self._get_target_timeframes(candle.timeframe)

        for tf in target_timeframes:
            aggregated = self._aggregate_candle(candle, tf)
            if aggregated:
                result.append(aggregated)

        return result[0] if len(result) == 1 else result

    def _get_target_timeframes(self, source_tf: Timeframe) -> list[Timeframe]:
        """获取目标时间周期"""
        mapping = {
            Timeframe.M1: [Timeframe.M5, Timeframe.M15, Timeframe.M30, Timeframe.H1, Timeframe.H4, Timeframe.D1],
        }
        return mapping.get(source_tf, [])

    def _aggregate_candle(self, source: Candle, target_tf: Timeframe) -> Optional[Candle]:
        """将K线聚合到目标周期"""
        bucket_size = target_tf.seconds * 1000
        target_bucket = (source.open_time // bucket_size) * bucket_size
        target_close = target_bucket + bucket_size - 1

        window = self.get_window(source.exchange, source.symbol, target_tf)

        if window.bucket == 0:
            window.bucket = target_bucket
            window.open = source.open
            window.high = source.high
            window.low = source.low
            window.close = source.close
            window.volume = source.volume
            window.quote_volume = source.quote_volume
            window.trade_count = source.trade_count
        else:
            if source.open_time < window.bucket:
                logger.warning(f"Out of order candle: {source.open_time} < {window.bucket}")
                return None

            if source.open_time >= window.bucket + bucket_size:
                closed_candle = self._close_window(window)
                window.reset()
                window.bucket = target_bucket
                window.open = source.open
                window.high = source.high
                window.low = source.low
                window.close = source.close
                window.volume = source.volume
                window.quote_volume = source.quote_volume
                window.trade_count = source.trade_count

                if closed_candle:
                    return closed_candle
                return None

            window.high = max(window.high, source.high)
            window.low = min(window.low, source.low)
            window.close = source.close
            window.volume += source.volume
            window.quote_volume += source.quote_volume
            window.trade_count += source.trade_count

        return None

    def _close_window(self, window: CandleWindow) -> Candle:
        """关闭并返回窗口"""
        return Candle(
            exchange=window.exchange,
            symbol=window.symbol,
            timeframe=window.timeframe,
            open_time=window.bucket,
            close_time=window.bucket + window.timeframe.seconds * 1000 - 1,
            open=window.open,
            high=window.high if window.high != float("-inf") else window.open,
            low=window.low if window.low != float("inf") else window.open,
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
            if window.bucket > 0 and not window.is_closed:
                candle = self._close_window(window)
                if candle:
                    closed.append(candle)
                window.reset()
        return closed

    def get_window_state(self, exchange: Exchange, symbol: str, timeframe: Timeframe) -> Optional[CandleWindow]:
        """获取窗口状态"""
        key = (exchange.value if isinstance(exchange, Exchange) else exchange, symbol, timeframe)
        return self.windows.get(key)


class TimeframeAggregator:
    """多时间周期聚合器"""

    def __init__(self):
        self.aggregators: Dict[Timeframe, CandleAggregator] = {}

    def get_aggregator(self, timeframe: Timeframe) -> CandleAggregator:
        if timeframe not in self.aggregators:
            self.aggregators[timeframe] = CandleAggregator()
        return self.aggregators[timeframe]

    def process(self, candle: Candle) -> list[Candle]:
        """处理K线，返回所有聚合结果"""
        results = []
        target_timeframes = self._get_target_timeframes(candle.timeframe)

        for tf in target_timeframes:
            agg = self.get_aggregator(tf)
            result = agg.process_candle(candle)
            if result:
                if isinstance(result, list):
                    results.extend(result)
                else:
                    results.append(result)

        return results

    def _get_target_timeframes(self, source_tf: Timeframe) -> list[Timeframe]:
        mapping = {
            Timeframe.M1: [Timeframe.M5, Timeframe.M15, Timeframe.M30, Timeframe.H1, Timeframe.H4, Timeframe.D1],
        }
        return mapping.get(source_tf, [])

    def close_all(self) -> list[Candle]:
        """关闭所有聚合器"""
        all_closed = []
        for agg in self.aggregators.values():
            closed = agg.close_all()
            all_closed.extend(closed)
        return all_closed


_aggregator: Optional[TimeframeAggregator] = None


def get_timeframe_aggregator() -> TimeframeAggregator:
    """获取全局时间周期聚合器"""
    global _aggregator
    if _aggregator is None:
        _aggregator = TimeframeAggregator()
    return _aggregator
