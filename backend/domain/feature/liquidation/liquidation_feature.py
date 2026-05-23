"""
Liquidation Feature Module - 清算/爆仓特征

核心特征：
- liquidation_cluster: 爆仓聚集
- liquidation_acceleration: 爆仓加速
- liquidation_chain_probability: 连锁爆仓概率
- long_short_liq_ratio: 多空爆仓结构
- liquidation_reversal_signal: 清算后反转信号
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import pandas as pd
import numpy as np

from domain.logging import get_logger

logger = get_logger("feature.liquidation")


@dataclass
class Liquidation:
    """爆仓数据"""
    timestamp: int
    symbol: str
    side: str  # 'long' or 'short'
    quantity: float
    price: float
    quote_quantity: float


@dataclass
class LiquidationFeature:
    """清算特征"""
    timestamp: int
    symbol: str
    exchange: str = "binance"

    # 基础特征
    liquidation_long: float = 0.0
    liquidation_short: float = 0.0
    liquidation_total: float = 0.0
    liquidation_spike: float = 0.0
    liquidation_pressure: float = 0.0
    long_liq_ratio: float = 0.0

    # 高级特征
    liquidation_cluster: float = 0.0
    liquidation_acceleration: float = 0.0
    liquidation_chain_probability: float = 0.0
    long_short_liq_ratio: float = 0.0
    liquidation_reversal_signal: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "liquidation_long": self.liquidation_long,
            "liquidation_short": self.liquidation_short,
            "liquidation_total": self.liquidation_total,
            "liquidation_spike": self.liquidation_spike,
            "liquidation_pressure": self.liquidation_pressure,
            "long_liq_ratio": self.long_liq_ratio,
            "liquidation_cluster": self.liquidation_cluster,
            "liquidation_acceleration": self.liquidation_acceleration,
            "liquidation_chain_probability": self.liquidation_chain_probability,
            "long_short_liq_ratio": self.long_short_liq_ratio,
            "liquidation_reversal_signal": self.liquidation_reversal_signal,
        }


class LiquidationFeatureExtractor:
    """清算特征提取器"""

    def __init__(self):
        self.liq_history: List[float] = []
        self.long_liq_history: List[float] = []
        self.short_liq_history: List[float] = []
        self.max_history = 60  # 60个周期

    def reset(self):
        """重置状态"""
        self.liq_history = []
        self.long_liq_history = []
        self.short_liq_history = []

    def extract_features(self, liquidations: List[Liquidation], window_ms: int = 60000) -> List[LiquidationFeature]:
        """提取清算特征"""
        if not liquidations:
            return []

        liquidations.sort(key=lambda l: l.timestamp)

        features = []
        window_start = liquidations[0].timestamp
        window_end = window_start + window_ms

        current_long = []
        current_short = []

        for liq in liquidations:
            if liq.timestamp >= window_end:
                feature = self._compute_window_feature(
                    symbol=liquidations[0].symbol,
                    long_liqs=current_long,
                    short_liqs=current_short,
                    window_end=window_end
                )
                if feature:
                    features.append(feature)

                window_start = window_end
                window_end = window_start + window_ms
                current_long = []
                current_short = []

            if liq.side == "long":
                current_long.append(liq)
            else:
                current_short.append(liq)

        if current_long or current_short:
            feature = self._compute_window_feature(
                symbol=liquidations[0].symbol,
                long_liqs=current_long,
                short_liqs=current_short,
                window_end=window_end
            )
            if feature:
                features.append(feature)

        return features

    def _compute_window_feature(
        self,
        symbol: str,
        long_liqs: List[Liquidation],
        short_liqs: List[Liquidation],
        window_end: int
    ) -> Optional[LiquidationFeature]:
        """计算窗口特征"""
        long_value = sum(l.quote_quantity for l in long_liqs)
        short_value = sum(l.quote_quantity for l in short_liqs)
        total_value = long_value + short_value

        self.long_liq_history.append(long_value)
        self.short_liq_history.append(short_value)
        self.liq_history.append(total_value)

        if len(self.liq_history) > self.max_history:
            self.liq_history.pop(0)
            self.long_liq_history.pop(0)
            self.short_liq_history.pop(0)

        # 爆仓尖峰
        liquidation_spike = 0.0
        if len(self.liq_history) >= 10:
            avg = np.mean(self.liq_history[:-1])
            std = np.std(self.liq_history[:-1]) if len(self.liq_history[:-1]) > 1 else 0.0
            if std > 0:
                liquidation_spike = (total_value - avg) / std

        # 爆仓压力
        liquidation_pressure = long_value - short_value

        # 多空爆仓比例
        long_liq_ratio = long_value / total_value if total_value > 0 else 0.5
        long_short_liq_ratio = long_value / short_value if short_value > 0 else (float('inf') if long_value > 0 else 1.0)

        # 爆仓聚集
        liquidation_cluster = 0.0
        if len(self.liq_history) >= 5:
            recent = self.liq_history[-5:]
            cluster_score = np.sum(recent) / (np.mean(self.liq_history) * 5) if np.mean(self.liq_history) > 0 else 0.0
            liquidation_cluster = min(1.0, cluster_score)

        # 爆仓加速
        liquidation_acceleration = 0.0
        if len(self.liq_history) >= 3:
            recent_trend = np.polyfit(range(3), self.liq_history[-3:], 1)[0]
            liquidation_acceleration = recent_trend / (np.mean(self.liq_history) + 1e-10)

        # 连锁爆仓概率
        chain_prob = 0.0
        if liquidation_spike > 2.0 and liquidation_acceleration > 0.5:
            chain_prob = min(1.0, (liquidation_spike + liquidation_acceleration) / 4.0)

        # 清算后反转信号
        reversal_signal = 0.0
        if liquidation_spike > 3.0:
            reversal_signal = -np.sign(liquidation_pressure) * (1.0 - chain_prob * 0.5)

        return LiquidationFeature(
            timestamp=window_end,
            symbol=symbol,
            liquidation_long=long_value,
            liquidation_short=short_value,
            liquidation_total=total_value,
            liquidation_spike=liquidation_spike,
            liquidation_pressure=liquidation_pressure,
            long_liq_ratio=long_liq_ratio,
            liquidation_cluster=liquidation_cluster,
            liquidation_acceleration=liquidation_acceleration,
            liquidation_chain_probability=chain_prob,
            long_short_liq_ratio=long_short_liq_ratio,
            liquidation_reversal_signal=reversal_signal,
        )


def extract_liquidation_features_from_df(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """从DataFrame提取清算特征"""
    extractor = LiquidationFeatureExtractor()

    liquidations = []
    for _, row in df.iterrows():
        timestamp_val = row.get("timestamp", row.get("time", 0))
        if isinstance(timestamp_val, pd.Timestamp):
            timestamp_ms = int(timestamp_val.timestamp() * 1000)
        else:
            timestamp_ms = int(timestamp_val)

        liq = Liquidation(
            timestamp=timestamp_ms,
            symbol=symbol,
            side="long" if row.get("side", "").lower() == "long" else "short",
            quantity=float(row.get("qty", row.get("quantity", 0))),
            price=float(row.get("price", 0)),
            quote_quantity=float(row.get("quote_qty", row.get("quote_quantity", 0))),
        )
        liquidations.append(liq)

    features = extractor.extract_features(liquidations)

    if not features:
        return pd.DataFrame()

    return pd.DataFrame([f.to_dict() for f in features])


def extract_liquidation_features(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """提取清算特征（与extract_liquidation_features_from_df相同，为兼容性保留）"""
    return extract_liquidation_features_from_df(df, symbol)
