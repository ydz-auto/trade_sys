"""
RSI (Relative Strength Index) - 相对强弱指标
"""

import pandas as pd
import numpy as np
from engines.compute.feature.contracts import TechnicalFeature


class RSI7Feature(TechnicalFeature):
    """RSI 7 周期"""
    name = "rsi_7"
    description = "Relative Strength Index 7-period"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)
        avg_gain = gain.rolling(7).mean()
        avg_loss = loss.rolling(7).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))


class RSI14Feature(TechnicalFeature):
    """RSI 14 周期"""
    name = "rsi_14"
    description = "Relative Strength Index 14-period"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)
        avg_gain = gain.rolling(14).mean()
        avg_loss = loss.rolling(14).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))


class RSI21Feature(TechnicalFeature):
    """RSI 21 周期"""
    name = "rsi_21"
    description = "Relative Strength Index 21-period"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)
        avg_gain = gain.rolling(21).mean()
        avg_loss = loss.rolling(21).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))
