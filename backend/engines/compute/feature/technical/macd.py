"""
MACD (Moving Average Convergence Divergence) - 移动平均收敛发散指标
"""

import pandas as pd
from engines.compute.feature.contracts import TechnicalFeature


class MACDFeature(TechnicalFeature):
    """MACD 指标"""
    name = "macd"
    description = "Moving Average Convergence Divergence"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        ema_fast = close.ewm(span=12, adjust=False).mean()
        ema_slow = close.ewm(span=26, adjust=False).mean()
        return ema_fast - ema_slow


class MACDSignalFeature(TechnicalFeature):
    """MACD Signal 线"""
    name = "macd_signal"
    description = "MACD Signal Line (9-period EMA of MACD)"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        ema_fast = close.ewm(span=12, adjust=False).mean()
        ema_slow = close.ewm(span=26, adjust=False).mean()
        macd = ema_fast - ema_slow
        return macd.ewm(span=9, adjust=False).mean()


class MACDHistFeature(TechnicalFeature):
    """MACD 柱状图"""
    name = "macd_hist"
    description = "MACD Histogram"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        ema_fast = close.ewm(span=12, adjust=False).mean()
        ema_slow = close.ewm(span=26, adjust=False).mean()
        macd = ema_fast - ema_slow
        macd_signal = macd.ewm(span=9, adjust=False).mean()
        return macd - macd_signal
