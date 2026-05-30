"""
Regime Features - 市场状态特征
Trend, Volatility, Market State
"""

import pandas as pd
import numpy as np
from engines.compute.feature.contracts import RegimeFeature


class HighVolatilityFeature(RegimeFeature):
    name = "high_volatility"
    description = "高波动率状态"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        vol_z = df.get("volatility_zscore", pd.Series(0.0, index=df.index))
        vol_z = vol_z.fillna(0)
        return (vol_z > 1.5).astype(float)


class LowLiquidityFeature(RegimeFeature):
    name = "low_liquidity"
    description = "低流动性状态"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        vol_z = df.get("volume_zscore", pd.Series(0.0, index=df.index))
        return (vol_z.fillna(0) < -1.5).astype(float)


class TrendRegimeFeature(RegimeFeature):
    name = "trend_regime"
    description = "趋势状态"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        trend = df.get("trend_20", pd.Series(0.0, index=df.index))
        trend = trend.fillna(0)
        return pd.Series(np.where(
            trend > 0.01, "trend",
            np.where(trend < -0.01, "trend", "chop"),
        ), index=df.index)


class VolatilityRegimeFeature(RegimeFeature):
    name = "volatility_regime"
    description = "波动率状态"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        vol_z = df.get("volatility_zscore", pd.Series(0.0, index=df.index))
        vol_z = vol_z.fillna(0)
        return pd.Series(np.where(
            vol_z > 2.0, "extreme",
            np.where(vol_z > 1.0, "high",
                     np.where(vol_z < -1.0, "low", "normal")),
        ), index=df.index)


class ExtremeMoveFeature(RegimeFeature):
    name = "extreme_move"
    description = "极端价格移动"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        ret = df.get("ret_1", pd.Series(0.0, index=df.index))
        ret = ret.fillna(0)
        ret_std = ret.rolling(100).std().fillna(0)
        return (ret.abs() > 3 * ret_std).astype(float)


class RegimeChangeFeature(RegimeFeature):
    name = "regime_change"
    description = "状态变化"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        trend_regime = df.get("trend_regime", None)
        if trend_regime is None:
            return pd.Series(0.0, index=df.index)
        return (trend_regime != trend_regime.shift(1)).astype(float)


class RiskMultiplierFeature(RegimeFeature):
    name = "risk_multiplier"
    description = "风险乘数"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        high_vol = df.get("high_volatility", pd.Series(0.0, index=df.index))
        return np.where(high_vol > 0, 0.5, 1.0)


class RiskOnOffFeature(RegimeFeature):
    name = "risk_on_off"
    description = "风险开关"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        trend = df.get("trend_20", pd.Series(0.0, index=df.index))
        vol_z = df.get("volatility_zscore", pd.Series(0.0, index=df.index))
        return (
            np.sign(trend.fillna(0))
            * (1 - vol_z.fillna(0).clip(-3, 3) / 3.0)
        )


class PrimaryRegimeFeature(RegimeFeature):
    name = "primary_regime"
    description = "主要市场状态"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        tr = df.get("trend_regime", pd.Series("chop", index=df.index))
        vr = df.get("volatility_regime", pd.Series("normal", index=df.index))
        tr = pd.Series(tr).fillna("chop")
        vr = pd.Series(vr).fillna("normal")

        return pd.Series(np.where(
            vr == "extreme", "panic",
            np.where(
                (tr == "trend") & (vr == "high"), "squeeze",
                np.where(
                    tr == "trend", "trend",
                    np.where(vr == "high", "high_leverage", "neutral"),
                ),
            ),
        ), index=df.index)


class RegimeRiskLevelFeature(RegimeFeature):
    name = "regime_risk_level"
    description = "状态风险等级"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        vol_z = df.get("volatility_zscore", pd.Series(0.0, index=df.index))
        return vol_z.fillna(0).clip(-3, 3).abs() / 3.0


class PositionSizingMultiplierFeature(RegimeFeature):
    name = "position_sizing_multiplier"
    description = "仓位规模乘数"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        risk_level = df.get("regime_risk_level", pd.Series(0.5, index=df.index))
        return 1.0 - risk_level * 0.5
