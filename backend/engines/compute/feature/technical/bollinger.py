"""
Bollinger Bands - 布林带指标
"""

import pandas as pd
from engines.compute.feature.contracts import TechnicalFeature


class BBandsFeature(TechnicalFeature):
    """Bollinger Bands"""
    name = "bb_bands"
    description = "Bollinger Bands (20-period, 2 std)"

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        close = df["close"]
        sma_20 = close.rolling(20).mean()
        std_20 = close.rolling(20).std()

        upper = sma_20 + 2 * std_20
        middle = sma_20
        lower = sma_20 - 2 * std_20

        return pd.DataFrame({
            "bb_upper": upper,
            "bb_middle": middle,
            "bb_lower": lower,
        })


class BBUpperFeature(TechnicalFeature):
    """布林带上轨"""
    name = "bb_upper"
    description = "Bollinger Upper Band"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        sma_20 = close.rolling(20).mean()
        std_20 = close.rolling(20).std()
        return sma_20 + 2 * std_20


class BBMiddleFeature(TechnicalFeature):
    """布林带中轨"""
    name = "bb_middle"
    description = "Bollinger Middle Band (SMA)"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return df["close"].rolling(20).mean()


class BBLowerFeature(TechnicalFeature):
    """布林带下轨"""
    name = "bb_lower"
    description = "Bollinger Lower Band"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        sma_20 = close.rolling(20).mean()
        std_20 = close.rolling(20).std()
        return sma_20 - 2 * std_20


class BBWidthFeature(TechnicalFeature):
    """布林带宽度"""
    name = "bb_width"
    description = "Bollinger Band Width"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        sma_20 = close.rolling(20).mean()
        std_20 = close.rolling(20).std()
        upper = sma_20 + 2 * std_20
        lower = sma_20 - 2 * std_20
        return (upper - lower) / sma_20.replace(0, pd.NA)
