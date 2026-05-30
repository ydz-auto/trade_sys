"""
Volatility Features - 波动率特征
"""

import pandas as pd
import numpy as np
from engines.compute.feature.contracts import TechnicalFeature


class Volatility20Feature(TechnicalFeature):
    """波动率 20 周期 (年化)"""
    name = "vol_20"
    description = "Annualized Volatility 20-period"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        ret = df["close"].pct_change()
        return ret.rolling(20).std() * np.sqrt(24 * 365)


class Volatility60Feature(TechnicalFeature):
    """波动率 60 周期 (年化)"""
    name = "vol_60"
    description = "Annualized Volatility 60-period"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        ret = df["close"].pct_change()
        return ret.rolling(60).std() * np.sqrt(24 * 365)


class RealizedVolatilityFeature(TechnicalFeature):
    """已实现波动率"""
    name = "realized_vol"
    description = "Realized Volatility"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        ret = df["close"].pct_change()
        return ret.rolling(60).std() * np.sqrt(24 * 365)


class VolatilityZScoreFeature(TechnicalFeature):
    """波动率 Z-Score"""
    name = "volatility_zscore"
    description = "Volatility Z-Score"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        ret = df["close"].pct_change()
        vol = ret.rolling(20).std() * np.sqrt(24 * 365)
        vol_mean = vol.rolling(100).mean()
        vol_std = vol.rolling(100).std()
        return (vol - vol_mean) / vol_std.replace(0, pd.NA)
