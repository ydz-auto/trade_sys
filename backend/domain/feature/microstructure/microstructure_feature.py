"""
Microstructure Feature Module - 微结构特征

核心特征（由Trade生成的合成盘口特征）：
- spread_estimate: 价差估计
- microprice_estimate: 微价格估计
- imbalance_1: 盘口失衡(1档)
- depth_pressure: 深度压力
- liquidity_shift: 流动性转移
- wall_detection: 大单成交检测
- spoof_probability: 异常撤单行为推测
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import pandas as pd
import numpy as np

from domain.logging import get_logger

logger = get_logger("feature.microstructure")


@dataclass
class MicrostructureFeature:
    """微结构特征"""
    timestamp: int
    symbol: str = "UNKNOWN"
    exchange: str = "binance"

    spread_estimate: float = 0.0
    spread_pct_estimate: float = 0.0
    microprice_estimate: float = 0.0
    mid_price: float = 0.0

    imbalance_1: float = 0.0
    imbalance_5: float = 0.0
    imbalance_10: float = 0.0
    imbalance_slope: float = 0.0

    depth_pressure: float = 0.0
    depth_ratio: float = 0.0
    depth_change: float = 0.0

    liquidity_shift: float = 0.0
    liquidity_vacuum: float = 0.0

    wall_detection: float = 0.0
    spoof_probability: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "spread_estimate": self.spread_estimate,
            "spread_pct_estimate": self.spread_pct_estimate,
            "microprice_estimate": self.microprice_estimate,
            "mid_price": self.mid_price,
            "imbalance_1": self.imbalance_1,
            "imbalance_5": self.imbalance_5,
            "imbalance_10": self.imbalance_10,
            "imbalance_slope": self.imbalance_slope,
            "depth_pressure": self.depth_pressure,
            "depth_ratio": self.depth_ratio,
            "depth_change": self.depth_change,
            "liquidity_shift": self.liquidity_shift,
            "liquidity_vacuum": self.liquidity_vacuum,
            "wall_detection": self.wall_detection,
            "spoof_probability": self.spoof_probability,
        }


class MicrostructureFeatureExtractor:
    """微结构特征提取器"""

    def __init__(self):
        self.price_history: List[float] = []
        self.volume_history: List[float] = []
        self.trade_delta_history: List[float] = []
        self.prev_feature: Optional[MicrostructureFeature] = None
        self.wall_threshold = 50000.0

    def reset(self):
        """重置状态"""
        self.price_history = []
        self.volume_history = []
        self.trade_delta_history = []
        self.prev_feature = None

    def extract_features(self, trades: pd.DataFrame, symbol: str = "UNKNOWN", window_ms: int = 60000) -> pd.DataFrame:
        """从交易数据提取微结构特征"""
        if trades.empty:
            return pd.DataFrame()

        trades = trades.sort_values("timestamp").copy()

        if "timestamp" not in trades.columns:
            raise ValueError("DataFrame must contain 'timestamp' column")

        def to_ms(ts):
            if isinstance(ts, pd.Timestamp):
                return int(ts.timestamp() * 1000)
            elif isinstance(ts, datetime):
                return int(ts.timestamp() * 1000)
            return int(ts)

        trades["timestamp"] = trades["timestamp"].apply(to_ms)
        trades = trades.sort_values("timestamp")

        results = []
        timestamps = sorted(trades["timestamp"].unique())

        for ts in timestamps:
            window_data = trades[trades["timestamp"] <= ts]
            if len(window_data) == 0:
                continue

            feature = self._compute_feature(window_data, ts, symbol)
            results.append(feature.to_dict())

        return pd.DataFrame(results)

    def _compute_feature(self, window_data: pd.DataFrame, timestamp: int, symbol: str = "UNKNOWN") -> MicrostructureFeature:
        """计算单个时间点的微结构特征"""
        buys = window_data[~window_data["is_buyer_maker"]]
        sells = window_data[window_data["is_buyer_maker"]]

        buy_volume = buys["qty"].sum()
        sell_volume = sells["qty"].sum()
        buy_value = buys["quote_qty"].sum()
        sell_value = sells["quote_qty"].sum()

        total_volume = buy_volume + sell_volume
        total_value = buy_value + sell_value

        vwap = total_value / total_volume if total_volume > 0 else window_data["price"].mean()
        mid_price = vwap

        self.price_history.append(vwap)
        self.volume_history.append(total_volume)
        self.trade_delta_history.append(buy_volume - sell_volume)

        if len(self.price_history) > 100:
            self.price_history.pop(0)
            self.volume_history.pop(0)
            self.trade_delta_history.pop(0)

        price_std = np.std(self.price_history) if len(self.price_history) > 1 else 0.0
        spread_estimate = price_std * 2
        spread_pct_estimate = spread_estimate / mid_price if mid_price > 0 else 0.0

        trade_delta = buy_volume - sell_volume
        microprice_estimate = mid_price * (1 + trade_delta / (total_volume + 1e-10) * 0.0001)

        imbalance_1 = (buy_volume - sell_volume) / (total_volume + 1e-10)

        recent_buys = buys.tail(5)
        recent_sells = sells.tail(5)
        imbalance_5 = (recent_buys["qty"].sum() - recent_sells["qty"].sum()) / (recent_buys["qty"].sum() + recent_sells["qty"].sum() + 1e-10)

        recent_buys_10 = buys.tail(10)
        recent_sells_10 = sells.tail(10)
        imbalance_10 = (recent_buys_10["qty"].sum() - recent_sells_10["qty"].sum()) / (recent_buys_10["qty"].sum() + recent_sells_10["qty"].sum() + 1e-10)

        imbalance_slope = 0.0
        if self.prev_feature:
            imbalance_slope = imbalance_10 - self.prev_feature.imbalance_10

        depth_pressure = imbalance_10 * total_volume

        depth_ratio = buy_volume / sell_volume if sell_volume > 0 else (float('inf') if buy_volume > 0 else 1.0)

        depth_change = 0.0
        if self.prev_feature:
            prev_depth = self.prev_feature.depth_ratio
            depth_change = (depth_ratio - prev_depth) / (prev_depth + 1e-10)

        liquidity_shift = trade_delta / (total_volume + 1e-10)

        liquidity_vacuum = 0.0
        if len(self.volume_history) >= 10:
            avg_volume = np.mean(self.volume_history[:-1])
            if avg_volume > 0:
                liquidity_vacuum = max(0, avg_volume - total_volume) / avg_volume

        wall_detection = 0.0
        large_trades = window_data[window_data["quote_qty"] >= self.wall_threshold]
        if len(large_trades) > 0:
            wall_detection = large_trades["quote_qty"].sum() / total_value if total_value > 0 else 0.0

        spoof_probability = 0.0
        if wall_detection > 0.3 and trade_delta < 0:
            spoof_probability = min(1.0, wall_detection * 2)

        feature = MicrostructureFeature(
            timestamp=timestamp,
            symbol=symbol,
            spread_estimate=spread_estimate,
            spread_pct_estimate=spread_pct_estimate,
            microprice_estimate=microprice_estimate,
            mid_price=mid_price,
            imbalance_1=imbalance_1,
            imbalance_5=imbalance_5,
            imbalance_10=imbalance_10,
            imbalance_slope=imbalance_slope,
            depth_pressure=depth_pressure,
            depth_ratio=depth_ratio,
            depth_change=depth_change,
            liquidity_shift=liquidity_shift,
            liquidity_vacuum=liquidity_vacuum,
            wall_detection=wall_detection,
            spoof_probability=spoof_probability,
        )

        self.prev_feature = feature
        return feature


def extract_microstructure_features(trades_df: pd.DataFrame, symbol: str = "UNKNOWN") -> pd.DataFrame:
    """从交易DataFrame提取微结构特征"""
    extractor = MicrostructureFeatureExtractor()
    return extractor.extract_features(trades_df, symbol=symbol)
