"""
Microstructure Features - 微观结构特征
Order Flow, Liquidity, Imbalance
"""

import pandas as pd
import numpy as np
from engines.compute.feature.contracts import MicrostructureFeature


class SpreadEstimateFeature(MicrostructureFeature):
    name = "spread_estimate"
    description = "价差估计"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return df.get("spread_estimate", pd.Series(np.nan, index=df.index))


class SpreadPctEstimateFeature(MicrostructureFeature):
    name = "spread_pct_estimate"
    description = "百分比价差估计"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return df.get("spread_pct_estimate", pd.Series(np.nan, index=df.index))


class MicropriceEstimateFeature(MicrostructureFeature):
    name = "microprice_estimate"
    description = "微价格估计"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return df.get("microprice_estimate", pd.Series(np.nan, index=df.index))


class Imbalance1Feature(MicrostructureFeature):
    name = "imbalance_1"
    description = "买卖不平衡 (即时)"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return df.get("imbalance_1", pd.Series(np.nan, index=df.index))


class Imbalance10Feature(MicrostructureFeature):
    name = "imbalance_10"
    description = "买卖不平衡 (10 周期 MA)"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        imb1 = df.get("imbalance_1", pd.Series(np.nan, index=df.index))
        return imb1.rolling(10).mean()


class ImbalanceSlopeFeature(MicrostructureFeature):
    name = "imbalance_slope"
    description = "买卖不平衡变化斜率"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        imb1 = df.get("imbalance_1", pd.Series(np.nan, index=df.index))
        return imb1.diff()


class DepthPressureFeature(MicrostructureFeature):
    name = "depth_pressure"
    description = "深度压力"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        imb1 = df.get("imbalance_1", pd.Series(np.nan, index=df.index))
        vol = df.get("volume", pd.Series(np.nan, index=df.index))
        return imb1 * vol


class DepthChangeFeature(MicrostructureFeature):
    name = "depth_change"
    description = "深度变化百分比"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        imb1 = df.get("imbalance_1", pd.Series(np.nan, index=df.index))
        return imb1.pct_change()


class LiquidityShiftFeature(MicrostructureFeature):
    name = "liquidity_shift"
    description = "流动性转移"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return df.get("liquidity_shift", pd.Series(np.nan, index=df.index))


class SpoofProbabilityFeature(MicrostructureFeature):
    name = "spoof_probability"
    description = "虚假交易概率"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return df.get("spoof_probability", pd.Series(0.0, index=df.index))


class WallDetectionFeature(MicrostructureFeature):
    name = "wall_detection"
    description = "大单墙检测"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return df.get("wall_detection", pd.Series(0.0, index=df.index))
