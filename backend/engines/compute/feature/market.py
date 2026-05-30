"""
Market Features - 市场数据特征
Funding, Open Interest, Basis
"""

import pandas as pd
import numpy as np
from engines.compute.feature.contracts import MarketFeature


class FundingRateFeature(MarketFeature):
    name = "funding_rate"
    description = "资金费率"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return df.get("funding_rate", pd.Series(np.nan, index=df.index))


class FundingZScoreFeature(MarketFeature):
    name = "funding_zscore"
    description = "资金费率 Z-score"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        fr = df.get("funding_rate", pd.Series(np.nan, index=df.index))
        fr_ma = fr.rolling(100).mean()
        fr_std = fr.rolling(100).std()
        return (fr - fr_ma) / fr_std.replace(0, np.nan)


class FundingExtremePositiveFeature(MarketFeature):
    name = "funding_extreme_positive"
    description = "极高资金费率"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        fr_z = df.get("funding_zscore", pd.Series(0.0, index=df.index))
        return (fr_z > 2).astype(float)


class FundingExtremeReversalFeature(MarketFeature):
    name = "funding_extreme_reversal"
    description = "资金费率极端反转信号"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        fr_z = df.get("funding_zscore", pd.Series(0.0, index=df.index))
        fr = df.get("funding_rate", pd.Series(0.0, index=df.index))
        return np.where(
            fr_z.abs() > 2.5,
            -np.sign(fr) * fr_z.abs() / 3.0,
            0.0,
        )


class FundingExplosionFeature(MarketFeature):
    name = "funding_explosion"
    description = "资金费率爆发"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        fr_z = df.get("funding_zscore", pd.Series(0.0, index=df.index))
        return (fr_z.abs() > 3).astype(float)


class OpenInterestFeature(MarketFeature):
    name = "oi"
    description = "持仓量"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return df.get("oi", pd.Series(np.nan, index=df.index))


class OIChangePctFeature(MarketFeature):
    name = "oi_change_pct"
    description = "持仓量变化百分比"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        oi = df.get("oi", pd.Series(np.nan, index=df.index))
        return oi.pct_change()


class OIZScoreFeature(MarketFeature):
    name = "oi_zscore"
    description = "持仓量 Z-score"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        oi = df.get("oi", pd.Series(np.nan, index=df.index))
        oi_ma = oi.rolling(100).mean()
        oi_std = oi.rolling(100).std()
        return (oi - oi_ma) / oi_std.replace(0, np.nan)


class OIFundingDivergenceFeature(MarketFeature):
    name = "oi_funding_divergence"
    description = "持仓量与资金费率背离"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        oi = df.get("oi", pd.Series(np.nan, index=df.index))
        fr = df.get("funding_rate", pd.Series(np.nan, index=df.index))
        oi_chg = oi.pct_change()
        fr_chg = fr.diff()

        oi_pos = oi_chg > 0
        fr_pos = fr > 0
        oi_neg = oi_chg < 0
        fr_neg = fr < 0

        return np.where(
            (oi_pos & fr_neg) | (oi_neg & fr_pos),
            np.abs(oi_chg) * np.abs(fr),
            0.0,
        )


class OISqueezeProbabilityFeature(MarketFeature):
    name = "oi_squeeze_probability"
    description = "OI 爆仓概率"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        oi_z = df.get("oi_zscore", pd.Series(0.0, index=df.index))
        fr_z = df.get("funding_zscore", pd.Series(0.0, index=df.index))
        return np.where(
            (oi_z.abs() > 1.5) & (fr_z.abs() > 1.5),
            np.minimum(1.0, (oi_z.abs() + fr_z.abs()) / 6.0),
            0.0,
        )


class OILiquidityPressureFeature(MarketFeature):
    name = "oi_liq_pressure"
    description = "OI 流动性压力"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        oi = df.get("oi", pd.Series(np.nan, index=df.index))
        fr = df.get("funding_rate", pd.Series(np.nan, index=df.index))
        return oi * fr.abs()


class LeverageCrowdednessFeature(MarketFeature):
    name = "leverage_crowdedness"
    description = "杠杆拥挤度"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        oi_z = df.get("oi_zscore", pd.Series(0.0, index=df.index))
        fr_z = df.get("funding_zscore", pd.Series(0.0, index=df.index))
        return np.where(
            (oi_z > 1.5) & (fr_z > 1.5),
            (oi_z + fr_z) / 3.0,
            0.0,
        )
