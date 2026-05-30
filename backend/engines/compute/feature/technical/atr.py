"""
ATR (Average True Range) - 平均真实波幅
"""

import pandas as pd
from engines.compute.feature.contracts import TechnicalFeature


class ATR14Feature(TechnicalFeature):
    """ATR 14 周期"""
    name = "atr_14"
    description = "Average True Range 14-period"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        high = df["high"]
        low = df["low"]
        close = df["close"]

        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(14).mean()

    @property
    def alt_names(self) -> list[str]:
        """别名"""
        return ["atr"]
