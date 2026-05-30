"""
EMA (Exponential Moving Average) - 指数移动平均
"""

import pandas as pd
from engines.compute.feature.contracts import TechnicalFeature


class EMA10Feature(TechnicalFeature):
    """EMA 10 周期"""
    name = "ema_10"
    description = "Exponential Moving Average 10-period"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return df["close"].ewm(span=10, adjust=False).mean()


class EMA20Feature(TechnicalFeature):
    """EMA 20 周期"""
    name = "ema_20"
    description = "Exponential Moving Average 20-period"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return df["close"].ewm(span=20, adjust=False).mean()


class EMA50Feature(TechnicalFeature):
    """EMA 50 周期"""
    name = "ema_50"
    description = "Exponential Moving Average 50-period"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return df["close"].ewm(span=50, adjust=False).mean()
