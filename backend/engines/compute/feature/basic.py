"""
Basic Features - 基础特征 (收益、波动率、ATR、ZScore 等)
"""

import pandas as pd
import numpy as np
from engines.compute.feature.contracts import TechnicalFeature


class Return1Feature(TechnicalFeature):
    name = "ret_1"
    description = "1 周期收益率"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return df["close"].pct_change(1)


class Return3Feature(TechnicalFeature):
    name = "ret_3"
    description = "3 周期收益率"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return df["close"].pct_change(3)


class Return5Feature(TechnicalFeature):
    name = "ret_5"
    description = "5 周期收益率"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return df["close"].pct_change(5)


class Return10Feature(TechnicalFeature):
    name = "ret_10"
    description = "10 周期收益率"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return df["close"].pct_change(10)


class Return15Feature(TechnicalFeature):
    name = "ret_15"
    description = "15 周期收益率"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return df["close"].pct_change(15)


class Return20Feature(TechnicalFeature):
    name = "ret_20"
    description = "20 周期收益率"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return df["close"].pct_change(20)


class Return30Feature(TechnicalFeature):
    name = "ret_30"
    description = "30 周期收益率"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return df["close"].pct_change(30)


class Return60Feature(TechnicalFeature):
    name = "ret_60"
    description = "60 周期收益率"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return df["close"].pct_change(60)


class ChangePctFeature(TechnicalFeature):
    name = "change_pct"
    description = "变化百分比"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        if "ret_1" in df.columns:
            return df["ret_1"]
        return df["close"].pct_change(1)


class AtrPctFeature(TechnicalFeature):
    name = "atr_pct"
    description = "ATR 百分比"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        atr = df.get("atr_14", (df["high"] - df["low"]).rolling(14).mean())
        return atr / df["close"]


class AtrExpansionFeature(TechnicalFeature):
    name = "atr_expansion"
    description = "ATR 扩张"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        atr = df.get("atr_14", (df["high"] - df["low"]).rolling(14).mean())
        return atr / atr.rolling(60).mean()


class RealizedVolZScoreFeature(TechnicalFeature):
    name = "realized_vol_zscore"
    description = "已实现波动率 ZScore"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        if "volatility_zscore" in df.columns:
            return df["volatility_zscore"]
        return pd.Series(np.nan, index=df.index)


class VolumeZScoreFeature(TechnicalFeature):
    name = "volume_zscore"
    description = "成交量 ZScore（相对于历史分布）"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        if "volume" not in df.columns:
            return pd.Series(np.nan, index=df.index)
        
        vol = df["volume"]
        vol_ma = vol.rolling(50).mean()
        vol_std = vol.rolling(50).std()
        
        zscore = (vol - vol_ma) / vol_std
        return zscore.fillna(0)


class VolumeMaFeature(TechnicalFeature):
    name = "volume_ma"
    description = "成交量移动平均"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return df["volume"].rolling(100).mean()


class VolumeRatioFeature(TechnicalFeature):
    name = "volume_ratio"
    description = "成交量比率"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        vol = df["volume"]
        vol_ma = df.get("volume_ma", vol.rolling(100).mean())
        return vol / vol_ma


class Trend20Feature(TechnicalFeature):
    name = "trend_20"
    description = "20 周期趋势"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        sma_20 = close.rolling(20).mean()
        return (close - sma_20) / sma_20


class Trend60Feature(TechnicalFeature):
    name = "trend_60"
    description = "60 周期趋势"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        sma_60 = close.rolling(60).mean()
        return (close - sma_60) / sma_60


class SlopeFeature(TechnicalFeature):
    name = "slope"
    description = "斜率 (trend_20)"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        if "trend_20" in df.columns:
            return df["trend_20"]
        close = df["close"]
        sma_20 = close.rolling(20).mean()
        return (close - sma_20) / sma_20


class DrawdownFromHighFeature(TechnicalFeature):
    name = "drawdown_from_high"
    description = "从高点回撤"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        max_60 = close.rolling(60).max()
        return (close - max_60) / max_60


class DistanceFromHighFeature(TechnicalFeature):
    name = "distance_from_high"
    description = "距离高点"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        if "drawdown_from_high" in df.columns:
            return df["drawdown_from_high"]
        close = df["close"]
        max_60 = close.rolling(60).max()
        return (close - max_60) / max_60


class NewHigh60Feature(TechnicalFeature):
    name = "new_high_60"
    description = "60 周期新高"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        return (close >= close.rolling(60).max()).astype(float)


class NewHigh20Feature(TechnicalFeature):
    name = "new_high_20"
    description = "20 周期新高"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        return (close >= close.rolling(20).max()).astype(float)


class NewLow60Feature(TechnicalFeature):
    name = "new_low_60"
    description = "60 周期新低"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        return (close <= close.rolling(60).min()).astype(float)


class ParabolicRet10Feature(TechnicalFeature):
    name = "parabolic_ret_10"
    description = "抛物线 10 周期收益率"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        ret_1 = df.get("ret_1", df["close"].pct_change(1))
        return np.exp(np.log(1 + ret_1).rolling(10).sum()) - 1


class ParabolicRetZScoreFeature(TechnicalFeature):
    name = "parabolic_ret_zscore"
    description = "抛物线收益率 ZScore"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        parabolic = df.get("parabolic_ret_10", None)
        if parabolic is None:
            ret_1 = df.get("ret_1", df["close"].pct_change(1))
            parabolic = np.exp(np.log(1 + ret_1).rolling(10).sum()) - 1
        ma = parabolic.rolling(100).mean()
        std = parabolic.rolling(100).std()
        return (parabolic - ma) / std.replace(0, np.nan)


class RangePctFeature(TechnicalFeature):
    name = "range_pct"
    description = "K线波动范围百分比"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return (df["high"] - df["low"]) / df["low"].replace(0, np.nan)


class IsUpFeature(TechnicalFeature):
    name = "is_up"
    description = "是否上涨"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return (df["close"] > df["open"]).astype(float)


class IsDownFeature(TechnicalFeature):
    name = "is_down"
    description = "是否下跌"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return (df["close"] < df["open"]).astype(float)


class VolatilitySpikeFeature(TechnicalFeature):
    name = "volatility_spike"
    description = "波动率 Spike"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return df.get("volatility_zscore", pd.Series(0.0, index=df.index))


class HighVolumeDeclineFeature(TechnicalFeature):
    name = "high_volume_decline"
    description = "放量下跌"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        ret_1 = df.get("ret_1", df["close"].pct_change(1))
        vol_zscore = df.get("volume_zscore", pd.Series(0.0, index=df.index))
        return ((ret_1 < 0) & (vol_zscore > 1.5)).astype(float)


class Return1hFeature(TechnicalFeature):
    name = "return_1h"
    description = "1 小时收益率"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        # TODO: 需要了解 timeframe 上下文
        return df.get("ret_1", df["close"].pct_change(1))


class MomentumOverheatFeature(TechnicalFeature):
    name = "momentum_overheat"
    description = "动量过热"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        if "rsi_14" in df.columns:
            return (df["rsi_14"] > 80).astype(float)
        return pd.Series(0.0, index=df.index)


class BreakoutVolumeDecayFeature(TechnicalFeature):
    name = "breakout_volume_decay"
    description = "突破放量衰减"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        new_high = df.get("new_high_60", pd.Series(0.0, index=df.index))
        vol_ratio = df.get("volume_ratio", pd.Series(1.0, index=df.index))
        vol_ratio_ma = vol_ratio.rolling(5).mean()
        return ((new_high > 0) & (vol_ratio_ma < 0.8)).astype(float)


class DistanceFromMaFeature(TechnicalFeature):
    name = "distance_from_ma"
    description = "距离 MA"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return df.get("trend_20", pd.Series(np.nan, index=df.index))


class Return5PercentileFeature(TechnicalFeature):
    name = "ret_5_percentile"
    description = "5 周期收益率百分位"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        ret_5 = df.get("ret_5", df["close"].pct_change(5))
        return ret_5.rolling(100, min_periods=20).apply(
            lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False
        )


class VolumeSpikeUpFeature(TechnicalFeature):
    name = "volume_spike_up"
    description = "放量上涨"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        ret_1 = df.get("ret_1", df["close"].pct_change(1))
        vol_zscore = df.get("volume_zscore", pd.Series(0.0, index=df.index))
        return ((ret_1 > 0) & (vol_zscore > 1.5)).astype(float)
