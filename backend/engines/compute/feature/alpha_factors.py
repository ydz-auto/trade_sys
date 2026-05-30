"""
Alpha Factors - Alpha 独有的做空因子
这些因子专门用于 Alpha 策略，留在 research 层
"""

import pandas as pd
import numpy as np
from engines.compute.feature.contracts import TechnicalFeature


class DistanceFromMA20Feature(TechnicalFeature):
    name = "distance_from_ma20"
    description = "距离 MA20"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        sma20 = df.get("sma_20", close.rolling(20).mean())
        return (close - sma20) / sma20.replace(0, np.nan)


class DistanceFromMA60Feature(TechnicalFeature):
    name = "distance_from_ma60"
    description = "距离 MA60"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        sma60 = df.get("sma_60", close.rolling(60).mean())
        return (close - sma60) / sma60.replace(0, np.nan)


class DistanceFromVWAPFeature(TechnicalFeature):
    name = "distance_from_vwap"
    description = "距离 VWAP"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        if "vwap" in df.columns:
            return (close - df["vwap"]) / df["vwap"].replace(0, np.nan)
        else:
            typical = (df["high"] + df["low"] + close) / 3
            vwap = (typical * df["volume"]).cumsum() / df["volume"].cumsum()
            return (close - vwap) / vwap.replace(0, np.nan)


class ZScorePriceFeature(TechnicalFeature):
    name = "zscore_price"
    description = "价格 Z-score"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        price_ma100 = close.rolling(100).mean()
        price_std100 = close.rolling(100).std()
        return (close - price_ma100) / price_std100.replace(0, np.nan)


class MA20SlopeZScoreFeature(TechnicalFeature):
    name = "ma20_slope_zscore"
    description = "MA20 斜率 Z-score"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        ma20 = close.rolling(20).mean()
        ma20_slope = ma20.diff() / ma20.shift(1)
        return (ma20_slope - ma20_slope.rolling(100).mean()) / ma20_slope.rolling(100).std().replace(0, np.nan)


class PriceDeviationBandFeature(TechnicalFeature):
    name = "price_deviation_band"
    description = "价格偏离 Bollinger 上轨"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        if "bb_upper" in df.columns:
            return (close - df["bb_upper"]) / df["bb_upper"].replace(0, np.nan)
        return pd.Series(np.nan, index=df.index)


class Ret3AccelerationFeature(TechnicalFeature):
    name = "ret_3_acceleration"
    description = "3 周期收益加速度"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        ret3 = df.get("ret_3", df["close"].pct_change(3))
        return ret3 - ret3.shift(1)


class Ret5AccelerationFeature(TechnicalFeature):
    name = "ret_5_acceleration"
    description = "5 周期收益加速度"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        ret5 = df.get("ret_5", df["close"].pct_change(5))
        return ret5 - ret5.shift(1)


class Ret10AccelerationFeature(TechnicalFeature):
    name = "ret_10_acceleration"
    description = "10 周期收益加速度"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        ret10 = df.get("ret_10", df["close"].pct_change(10))
        return ret10 - ret10.shift(1)


class SlopeAccelerationFeature(TechnicalFeature):
    name = "slope_acceleration"
    description = "斜率加速度"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        slope = df.get("slope", (df["close"] - df["close"].rolling(20).mean()) / df["close"].rolling(20).mean())
        return slope - slope.shift(1)


class CurvatureFeature(TechnicalFeature):
    name = "curvature"
    description = "曲率（二阶导数）"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        ret3 = df.get("ret_3", df["close"].pct_change(3))
        return ret3.diff().diff()


class VelocityIncreaseFeature(TechnicalFeature):
    name = "velocity_increase"
    description = "速度增加"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        ret1 = df.get("ret_1", df["close"].pct_change(1))
        ret1_ma5 = ret1.rolling(5).mean()
        return ret1 - ret1_ma5


class MomentumDivergenceFeature(TechnicalFeature):
    name = "momentum_divergence"
    description = "动量背离"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        if "rsi_14" in df.columns and "new_high_60" in df.columns:
            return pd.Series(np.where(
                (df["new_high_60"] > 0) & (df["rsi_14"].shift(1) > df["rsi_14"]),
                df["rsi_14"].shift(1) - df["rsi_14"],
                0.0,
            ), index=df.index)
        return pd.Series(0.0, index=df.index)


class UpperShadowRatioFeature(TechnicalFeature):
    name = "upper_shadow_ratio"
    description = "上影线比例"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        if "upper_wick_pct" in df.columns:
            return df["upper_wick_pct"]
        return (df["high"] - np.maximum(df["open"], df["close"])) / df["low"].replace(0, np.nan)


class LowerShadowRatioFeature(TechnicalFeature):
    name = "lower_shadow_ratio"
    description = "下影线比例"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        if "lower_wick_pct" in df.columns:
            return df["lower_wick_pct"]
        return (np.minimum(df["open"], df["close"]) - df["low"]) / df["low"].replace(0, np.nan)


class BodyPctFeature(TechnicalFeature):
    name = "body_pct"
    description = "实体比例"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        if "body_pct" in df.columns:
            return df["body_pct"]
        return (df["close"] - df["open"]) / df["low"].replace(0, np.nan)


class ConsecutiveGreenFeature(TechnicalFeature):
    name = "consecutive_green"
    description = "连续阳线数量"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        if "consecutive_green" in df.columns:
            return df["consecutive_green"]
        is_up = (df["close"] > df["open"]).astype(float)
        return is_up.groupby((~is_up.astype(bool)).cumsum()).cumsum()


class ConsecutiveRedFeature(TechnicalFeature):
    name = "consecutive_red"
    description = "连续阴线数量"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        if "consecutive_red" in df.columns:
            return df["consecutive_red"]
        is_down = (df["close"] < df["open"]).astype(float)
        return is_down.groupby((~is_down.astype(bool)).cumsum()).cumsum()


class VolumeClimaxFeature(TechnicalFeature):
    name = "volume_climax"
    description = "成交量高潮"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        vol_z = df.get("volume_zscore", pd.Series(0.0, index=df.index))
        ret1 = df.get("ret_1", df["close"].pct_change(1))
        ret_std = ret1.abs().rolling(100).mean().fillna(0.001)
        return pd.Series(np.where(
            (vol_z.fillna(0) > 1.5) & (ret1.abs() > 2 * ret_std),
            vol_z.fillna(0) * ret1.abs(),
            0.0,
        ), index=df.index)


class TakerBuyClimaxFeature(TechnicalFeature):
    name = "taker_buy_climax"
    description = "主动买入高潮"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        if "taker_buy_ratio" in df.columns and "range_pct" in df.columns:
            vol_z = df.get("volume_zscore", pd.Series(0.0, index=df.index))
            return pd.Series(np.where(
                (df["taker_buy_ratio"] > 0.55) & (vol_z > 1.5) & (df["range_pct"] > df["range_pct"].rolling(100).mean()),
                df["taker_buy_ratio"] * vol_z,
                0.0,
            ), index=df.index)
        return pd.Series(0.0, index=df.index)


class NewHigh120Feature(TechnicalFeature):
    name = "new_high_120"
    description = "120 周期新高"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        if "new_high_120" in df.columns:
            return df["new_high_120"]
        close = df["close"]
        return (close >= close.rolling(120).max()).astype(float)


class BreakoutStrengthFeature(TechnicalFeature):
    name = "breakout_strength"
    description = "突破强度"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        atr = df.get("atr_14", (df["high"] - df["low"]).rolling(14).mean())
        rolling_high_60 = close.rolling(60).max().shift(1)
        return (close - rolling_high_60) / atr.replace(0, np.nan)


class BreakoutFailureFeature(TechnicalFeature):
    name = "breakout_failure"
    description = "突破失败"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        new_high_60 = df.get("new_high_60", (df["close"] >= df["close"].rolling(60).max()).astype(float))
        ret1 = df.get("ret_1", df["close"].pct_change(1))
        return pd.Series(np.where(
            (new_high_60 > 0) & (ret1 < 0),
            -ret1,
            0.0,
        ), index=df.index)


class BreakoutRetractionFeature(TechnicalFeature):
    name = "breakout_retraction"
    description = "突破回撤"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        breakout_str = df.get("breakout_strength", None)
        if breakout_str is None:
            close = df["close"]
            atr = df.get("atr_14", (df["high"] - df["low"]).rolling(14).mean())
            rolling_high_60 = close.rolling(60).max().shift(1)
            breakout_str = (close - rolling_high_60) / atr.replace(0, np.nan)
        ret1 = df.get("ret_1", df["close"].pct_change(1))
        return pd.Series(np.where(
            breakout_str.abs() > 0,
            -ret1 / breakout_str.abs(),
            0.0,
        ), index=df.index)


class DoubleTopProbabilityFeature(TechnicalFeature):
    name = "double_top_probability"
    description = "双顶概率"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        rolling_max = close.rolling(60).max()
        rolling_min = close.rolling(60).min()
        range_60 = rolling_max - rolling_min
        distance_from_high = (close - rolling_max) / range_60.replace(0, np.nan)
        return pd.Series(np.where(
            (distance_from_high.shift(1) > -0.05) & (distance_from_high < -0.1),
            (distance_from_high.shift(1) - distance_from_high).abs(),
            0.0,
        ), index=df.index)


class FailedReboundStrengthFeature(TechnicalFeature):
    name = "failed_rebound_strength"
    description = "反弹失败强度"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        return pd.Series(np.where(
            (close.shift(3) < close.shift(5)) & (close < close.shift(1)) & (close > close.shift(5)),
            (close.shift(5) - close) / close.shift(5),
            0.0,
        ), index=df.index)


class OIZScoreLongFeature(TechnicalFeature):
    name = "oi_zscore_long"
    description = "OI Z-score (多头)"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return df.get("oi_zscore", pd.Series(np.nan, index=df.index))


class BasisZScoreFeature(TechnicalFeature):
    name = "basis_zscore"
    description = "基差 Z-score"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        if "basis" in df.columns:
            basis = df["basis"]
            return (basis - basis.rolling(100).mean()) / basis.rolling(100).std().replace(0, np.nan)
        return pd.Series(np.nan, index=df.index)


class LongShortRatioFeature(TechnicalFeature):
    name = "long_short_ratio"
    description = "多空比"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        if "long_short_ratio" in df.columns:
            return df["long_short_ratio"]
        oi = df.get("oi", pd.Series(np.nan, index=df.index))
        oi_chg = oi.pct_change()
        return pd.Series(np.where(
            oi_chg > 0,
            1.0 + oi_chg.abs(),
            1.0 / (1.0 + oi_chg.abs()),
        ), index=df.index)


class LeverageRatioLongFeature(TechnicalFeature):
    name = "leverage_ratio_long"
    description = "杠杆比 (多头)"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        oi_z = df.get("oi_zscore", pd.Series(0.0, index=df.index))
        fr = df.get("funding_rate", pd.Series(0.0, index=df.index))
        return pd.Series(np.where(
            fr > 0,
            oi_z + (fr / 0.0001),
            oi_z,
        ), index=df.index)


class FundingOICombinedFeature(TechnicalFeature):
    name = "funding_oi_combined"
    description = "资金费率与 OI 组合信号"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        fr_z = df.get("funding_zscore", pd.Series(0.0, index=df.index))
        oi_z = df.get("oi_zscore", pd.Series(0.0, index=df.index))
        return pd.Series(np.where(
            (fr_z > 0) & (oi_z > 0),
            fr_z * oi_z,
            0.0,
        ), index=df.index)


class CrowdedLongScoreFeature(TechnicalFeature):
    name = "crowded_long_score"
    description = "拥挤多头分数"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        fr_z = df.get("funding_zscore", pd.Series(0.0, index=df.index))
        oi_z = df.get("oi_zscore", pd.Series(0.0, index=df.index))
        vol_z = df.get("volume_zscore", pd.Series(0.0, index=df.index))
        return (fr_z + oi_z + vol_z) / 3.0


class LiquidationRiskLongFeature(TechnicalFeature):
    name = "liquidation_risk_long"
    description = "多头爆仓风险"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return pd.Series(0.0, index=df.index)


class ShortSqueezeProbFeature(TechnicalFeature):
    name = "short_squeeze_prob"
    description = "空头挤压概率"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        oi_z = df.get("oi_zscore", pd.Series(0.0, index=df.index))
        fr = df.get("funding_rate", pd.Series(0.0, index=df.index))
        return pd.Series(np.where(
            (oi_z < -1) & (fr < 0),
            (-oi_z * fr.abs()) / 2,
            0.0,
        ), index=df.index)


class MarginUsageLongFeature(TechnicalFeature):
    name = "margin_usage_long"
    description = "多头保证金使用量"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return pd.Series(np.nan, index=df.index)
