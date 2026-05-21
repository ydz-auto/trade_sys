"""
Trade Feature Module - 交易特征提取器

核心特征：
- trade_delta: 主动买卖差
- cumulative_delta: 累积主动流
- aggressive_buy/sell_volume: 主动买卖量
- trade_velocity: 成交速度
- large_trade_ratio: 大单占比
- sweep_buy/sell_score: 扫单评分
- liquidity_vacuum: 流动性真空
- trade_imbalance: 买卖失衡
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import pandas as pd
import numpy as np

from infrastructure.logging import get_logger

logger = get_logger("feature.trade")


@dataclass
class Trade:
    """交易数据"""
    timestamp: int
    price: float
    quantity: float
    quote_quantity: float
    is_buyer_maker: bool
    trade_id: str


@dataclass
class TradeFeature:
    """交易特征"""
    timestamp: int
    symbol: str = "UNKNOWN"
    exchange: str = "binance"

    trade_delta: float = 0.0
    cumulative_delta: float = 0.0
    aggressive_buy_volume: float = 0.0
    aggressive_sell_volume: float = 0.0
    total_volume: float = 0.0
    total_value: float = 0.0
    num_trades: int = 0
    trade_velocity: float = 0.0
    avg_trade_size: float = 0.0
    max_trade_size: float = 0.0
    large_trade_ratio: float = 0.0
    large_trade_volume: float = 0.0
    sweep_buy_score: float = 0.0
    sweep_sell_score: float = 0.0
    liquidity_vacuum: float = 0.0
    trade_imbalance: float = 0.0
    buy_sell_ratio: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "trade_delta": self.trade_delta,
            "cumulative_delta": self.cumulative_delta,
            "aggressive_buy_volume": self.aggressive_buy_volume,
            "aggressive_sell_volume": self.aggressive_sell_volume,
            "total_volume": self.total_volume,
            "total_value": self.total_value,
            "num_trades": self.num_trades,
            "trade_velocity": self.trade_velocity,
            "avg_trade_size": self.avg_trade_size,
            "max_trade_size": self.max_trade_size,
            "large_trade_ratio": self.large_trade_ratio,
            "large_trade_volume": self.large_trade_volume,
            "sweep_buy_score": self.sweep_buy_score,
            "sweep_sell_score": self.sweep_sell_score,
            "liquidity_vacuum": self.liquidity_vacuum,
            "trade_imbalance": self.trade_imbalance,
            "buy_sell_ratio": self.buy_sell_ratio,
        }


class TradeFeatureExtractor:
    """交易特征提取器"""

    def __init__(self):
        self.cumulative_delta = 0.0
        self.prev_price = 0.0
        self.large_trade_threshold = 10000.0
        self.sweep_threshold = 0.001

    def reset(self):
        """重置状态"""
        self.cumulative_delta = 0.0
        self.prev_price = 0.0

    def extract_features(self, trades: List[Trade], symbol: str = "UNKNOWN", window_ms: int = 60000) -> List[TradeFeature]:
        """提取特征"""
        if not trades:
            return []

        trades.sort(key=lambda t: t.timestamp)

        features = []
        window_start = trades[0].timestamp
        window_end = window_start + window_ms

        current_buys = []
        current_sells = []
        large_trades = []

        for trade in trades:
            if trade.timestamp >= window_end:
                feature = self._compute_window_feature(
                    buys=current_buys,
                    sells=current_sells,
                    large_trades=large_trades,
                    window_end=window_end,
                    symbol=symbol
                )
                if feature:
                    features.append(feature)

                window_start = window_end
                window_end = window_start + window_ms
                current_buys = []
                current_sells = []
                large_trades = []

            if trade.is_buyer_maker:
                current_sells.append(trade)
            else:
                current_buys.append(trade)

            if trade.quote_quantity >= self.large_trade_threshold:
                large_trades.append(trade)

        if current_buys or current_sells:
            feature = self._compute_window_feature(
                buys=current_buys,
                sells=current_sells,
                large_trades=large_trades,
                window_end=window_end,
                symbol=symbol
            )
            if feature:
                features.append(feature)

        return features

    def _compute_window_feature(
        self,
        buys: List[Trade],
        sells: List[Trade],
        large_trades: List[Trade],
        window_end: int,
        symbol: str = "UNKNOWN"
    ) -> Optional[TradeFeature]:
        """计算窗口特征"""
        if not buys and not sells:
            return None

        buy_volume = sum(t.quantity for t in buys)
        sell_volume = sum(t.quantity for t in sells)
        buy_value = sum(t.quote_quantity for t in buys)
        sell_value = sum(t.quote_quantity for t in sells)

        total_volume = buy_volume + sell_volume
        total_value = buy_value + sell_value
        num_trades = len(buys) + len(sells)

        trade_delta = buy_volume - sell_volume
        self.cumulative_delta += trade_delta

        avg_trade_size = total_volume / num_trades if num_trades > 0 else 0.0
        max_trade_size = max(t.quantity for t in buys + sells) if (buys + sells) else 0.0

        large_trade_ratio = len(large_trades) / num_trades if num_trades > 0 else 0.0
        large_trade_volume = sum(t.quantity for t in large_trades)

        prices = [t.price for t in buys + sells]
        if prices:
            vwap = total_value / total_volume if total_volume > 0 else np.mean(prices)
            price_change = (prices[-1] - prices[0]) / prices[0] if prices[0] > 0 else 0.0
        else:
            vwap = 0.0
            price_change = 0.0

        sweep_buy_score = self._compute_sweep_score(buys, price_change)
        sweep_sell_score = self._compute_sweep_score(sells, -price_change)

        liquidity_vacuum = self._compute_liquidity_vacuum(buys + sells, vwap)

        buy_sell_ratio = buy_volume / sell_volume if sell_volume > 0 else (float('inf') if buy_volume > 0 else 1.0)
        trade_imbalance = (buy_volume - sell_volume) / (buy_volume + sell_volume) if total_volume > 0 else 0.0

        return TradeFeature(
            timestamp=window_end,
            symbol=symbol,
            trade_delta=trade_delta,
            cumulative_delta=self.cumulative_delta,
            aggressive_buy_volume=buy_volume,
            aggressive_sell_volume=sell_volume,
            total_volume=total_volume,
            total_value=total_value,
            num_trades=num_trades,
            trade_velocity=num_trades / 60.0,
            avg_trade_size=avg_trade_size,
            max_trade_size=max_trade_size,
            large_trade_ratio=large_trade_ratio,
            large_trade_volume=large_trade_volume,
            sweep_buy_score=sweep_buy_score,
            sweep_sell_score=sweep_sell_score,
            liquidity_vacuum=liquidity_vacuum,
            trade_imbalance=trade_imbalance,
            buy_sell_ratio=buy_sell_ratio,
        )

    def _compute_sweep_score(self, trades: List[Trade], price_change: float) -> float:
        """计算扫单评分"""
        if not trades:
            return 0.0

        large_trades = [t for t in trades if t.quote_quantity >= self.large_trade_threshold]
        if not large_trades:
            return 0.0

        large_value = sum(t.quote_quantity for t in large_trades)
        total_value = sum(t.quote_quantity for t in trades)

        intensity = large_value / total_value if total_value > 0 else 0.0
        direction = 1.0 if price_change > self.sweep_threshold else (-1.0 if price_change < -self.sweep_threshold else 0.0)

        return intensity * abs(price_change) * direction

    def _compute_liquidity_vacuum(self, trades: List[Trade], vwap: float) -> float:
        """计算流动性真空"""
        if not trades:
            return 0.0

        prices = [t.price for t in trades]
        spread = max(prices) - min(prices) if prices else 0.0
        spread_pct = spread / vwap if vwap > 0 else 0.0

        avg_time_between = 0.0
        if len(trades) > 1:
            times = sorted([t.timestamp for t in trades])
            gaps = [times[i+1] - times[i] for i in range(len(times)-1)]
            avg_time_between = np.mean(gaps)

        vacuum_score = spread_pct * (avg_time_between / 1000.0)
        return vacuum_score


def extract_trade_features_from_df(df: pd.DataFrame, symbol: str = "UNKNOWN") -> pd.DataFrame:
    """从DataFrame提取交易特征"""
    extractor = TradeFeatureExtractor()

    trades = []
    for _, row in df.iterrows():
        timestamp_val = row["timestamp"]
        if isinstance(timestamp_val, pd.Timestamp):
            timestamp_ms = int(timestamp_val.timestamp() * 1000)
        else:
            timestamp_ms = int(timestamp_val)

        trade = Trade(
            timestamp=timestamp_ms,
            price=float(row["price"]),
            quantity=float(row["qty"]),
            quote_quantity=float(row["quote_qty"]),
            is_buyer_maker=bool(row["is_buyer_maker"]),
            trade_id=str(row["id"]),
        )
        trades.append(trade)

    features = extractor.extract_features(trades, symbol=symbol)

    if not features:
        return pd.DataFrame()

    return pd.DataFrame([f.to_dict() for f in features])
