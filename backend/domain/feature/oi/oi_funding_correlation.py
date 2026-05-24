"""
OI + Funding Correlation Module - 杠杆结构联动特征

核心特征：
- oi_funding_divergence: OI增+Funding极端
- oi_squeeze_probability: 杠杆挤压概率
- oi_liq_pressure: 潜在踩踏压力
- funding_extreme_reversal: 情绪极值反转
- leverage_crowdedness: 杠杆拥挤度
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import pandas as pd
import numpy as np

import logging

logger = logging.getLogger(__name__)


@dataclass
class OIFeature:
    """持仓量特征"""
    timestamp: int
    symbol: str
    oi: float = 0.0
    oi_delta: float = 0.0
    oi_change: float = 0.0
    oi_zscore: float = 0.0


@dataclass
class FundingFeature:
    """资金费率特征"""
    timestamp: int
    symbol: str
    funding_rate: float = 0.0
    funding_zscore: float = 0.0
    funding_delta: float = 0.0


@dataclass
class OIFundingCorrelation:
    """OI + Funding 联动特征"""
    timestamp: int
    symbol: str
    exchange: str = "binance"

    # 联动特征
    oi_funding_divergence: float = 0.0
    oi_squeeze_probability: float = 0.0
    oi_liq_pressure: float = 0.0
    funding_extreme_reversal: float = 0.0
    leverage_crowdedness: float = 0.0

    # 输入特征（用于计算）
    oi: float = 0.0
    oi_zscore: float = 0.0
    funding_rate: float = 0.0
    funding_zscore: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "oi_funding_divergence": self.oi_funding_divergence,
            "oi_squeeze_probability": self.oi_squeeze_probability,
            "oi_liq_pressure": self.oi_liq_pressure,
            "funding_extreme_reversal": self.funding_extreme_reversal,
            "leverage_crowdedness": self.leverage_crowdedness,
            "oi": self.oi,
            "oi_zscore": self.oi_zscore,
            "funding_rate": self.funding_rate,
            "funding_zscore": self.funding_zscore,
        }


class OIFundingCorrelator:
    """OI + Funding 联动分析器
    重要：使用滚动窗口计算统计量，避免未来数据泄漏
    """

    def __init__(self):
        self.oi_history: List[float] = []
        self.funding_history: List[float] = []
        self.timestamp_history: List[int] = []
        self.max_history = 1008  # 7 days * 24h * 6 intervals
        self.lookback_window = 240  # 滚动窗口大小（避免全局统计）

    def add_data(self, oi: float, funding_rate: float, timestamp: int):
        """添加数据点"""
        self.oi_history.append(oi)
        self.funding_history.append(funding_rate)
        self.timestamp_history.append(timestamp)

        if len(self.oi_history) > self.max_history:
            self.oi_history.pop(0)
            self.funding_history.pop(0)
            self.timestamp_history.pop(0)

    def compute_correlation(self, oi: float, funding_rate: float, timestamp: int) -> OIFundingCorrelation:
        """计算联动特征
        关键：使用滚动窗口计算统计量，只使用历史数据，不泄漏未来
        """
        self.add_data(oi, funding_rate, timestamp)

        if len(self.oi_history) < 24:
            return OIFundingCorrelation(
                timestamp=timestamp,
                symbol="UNKNOWN",
                oi=oi,
                funding_rate=funding_rate,
            )

        # 使用滚动窗口计算统计量（只使用历史数据，不包含未来）
        window_size = min(self.lookback_window, len(self.oi_history))
        oi_window = np.array(self.oi_history[-window_size:])
        funding_window = np.array(self.funding_history[-window_size:])

        oi_mean = np.mean(oi_window)
        oi_std = np.std(oi_window)
        funding_mean = np.mean(funding_window)
        funding_std = np.std(funding_window)

        oi_zscore = (oi - oi_mean) / oi_std if oi_std > 0 else 0.0
        funding_zscore = (funding_rate - funding_mean) / funding_std if funding_std > 0 else 0.0

        # OI-Funding 背离：OI增加但Funding极端（正向或负向）
        recent_trend_window = min(24, len(self.oi_history))
        recent_oi = np.array(self.oi_history[-recent_trend_window:])
        recent_oi_trend = np.polyfit(range(len(recent_oi)), recent_oi, 1)[0] if len(recent_oi) >= 2 else 0.0
        oi_funding_divergence = recent_oi_trend * abs(funding_zscore)

        # 杠杆挤压概率：高OI + 极端Funding
        squeeze_prob = 0.0
        if abs(oi_zscore) > 1.5 and abs(funding_zscore) > 2.0:
            squeeze_prob = min(1.0, (abs(oi_zscore) + abs(funding_zscore)) / 5.0)

        # 潜在踩踏压力
        liq_pressure = oi_zscore * funding_zscore

        # Funding极端反转信号
        funding_extreme_reversal = 0.0
        if abs(funding_zscore) > 2.5:
            funding_extreme_reversal = -funding_zscore * 0.2

        # 杠杆拥挤度
        leverage_crowdedness = min(1.0, (abs(oi_zscore) + abs(funding_zscore)) / 4.0)

        return OIFundingCorrelation(
            timestamp=timestamp,
            symbol="UNKNOWN",
            oi_funding_divergence=oi_funding_divergence,
            oi_squeeze_probability=squeeze_prob,
            oi_liq_pressure=liq_pressure,
            funding_extreme_reversal=funding_extreme_reversal,
            leverage_crowdedness=leverage_crowdedness,
            oi=oi,
            oi_zscore=oi_zscore,
            funding_rate=funding_rate,
            funding_zscore=funding_zscore,
        )


def compute_oi_funding_correlation(
    oi_df: pd.DataFrame,
    funding_df: pd.DataFrame,
    symbol: str
) -> pd.DataFrame:
    """计算OI和Funding的联动特征"""
    correlator = OIFundingCorrelator()

    merged = pd.merge_asof(
        oi_df.sort_values("timestamp"),
        funding_df.sort_values("timestamp"),
        on="timestamp",
        direction="nearest"
    )

    results = []
    for _, row in merged.iterrows():
        if pd.notna(row["oi"]) and pd.notna(row["funding_rate"]):
            timestamp_val = int(row["timestamp"])
            corr = correlator.compute_correlation(
                oi=float(row["oi"]),
                funding_rate=float(row["funding_rate"]),
                timestamp=timestamp_val
            )
            corr.symbol = symbol
            results.append(corr.to_dict())

    return pd.DataFrame(results)


def extract_oi_funding_features(
    oi_df: pd.DataFrame,
    funding_df: pd.DataFrame,
    symbol: str
) -> pd.DataFrame:
    """提取OI和Funding特征（与compute_oi_funding_correlation相同，为兼容性保留）"""
    return compute_oi_funding_correlation(oi_df, funding_df, symbol)
