"""
SMA (Simple Moving Average) - 简单移动平均
"""

import pandas as pd
from engines.compute.feature.contracts import TechnicalFeature


class SMA10Feature(TechnicalFeature):
    """SMA 10 周期"""
    name = "sma_10"
    description = "Simple Moving Average 10-period"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return df["close"].rolling(10).mean()


class SMA20Feature(TechnicalFeature):
    """SMA 20 周期"""
    name = "sma_20"
    description = "Simple Moving Average 20-period"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return df["close"].rolling(20).mean()


class SMA50Feature(TechnicalFeature):
    """SMA 50 周期"""
    name = "sma_50"
    description = "Simple Moving Average 50-period"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return df["close"].rolling(50).mean()


class SMA100Feature(TechnicalFeature):
    """SMA 100 周期"""
    name = "sma_100"
    description = "Simple Moving Average 100-period"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return df["close"].rolling(100).mean()
