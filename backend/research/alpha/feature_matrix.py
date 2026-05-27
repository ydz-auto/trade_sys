"""
Feature Matrix - 特征矩阵构建
包含两个版本：
1. 尝试使用真实统一特征矩阵系统（domain.feature 层）
2. 回退到从FileDataLakeReader手动构建
"""

import sys
from pathlib import Path
from typing import Optional, List, Any

import pandas as pd
import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def build_feature_matrix(
    symbol: str = "BTCUSDT",
    exchange: str = "binance",
    days: int = 90,
    timeframe: str = "1h",
) -> pd.DataFrame:
    """
    构建特征矩阵

    Args:
        symbol: 交易对
        exchange: 交易所
        days: 回看天数
        timeframe: K线周期

    Returns:
        特征矩阵 DataFrame
    """
    # 先尝试真实特征矩阵系统
    try:
        from domain.feature.feature_matrix import get_historical_feature_matrix
        from engines.compute.feature.historical_materializer import HistoricalFeatureMaterializer

        end_ts = int(pd.Timestamp.now().timestamp() * 1000)
        start_ts = int((pd.Timestamp.now() - pd.Timedelta(days=days)).timestamp() * 1000)
        interval_ms = _timeframe_to_ms(timeframe)

        data_lake = BACKEND_ROOT / "data_lake"
        materializer = HistoricalFeatureMaterializer(data_lake)

        matrix = materializer.materialize_symbol(
            symbol=symbol,
            interval_ms=interval_ms,
            start_ts=start_ts,
            end_ts=end_ts,
            force=False
        )

        if matrix is not None and len(matrix.timestamps) > 0:
            df = matrix.to_dataframe()
            print(f"  真实特征矩阵: {len(df.columns)}列 × {len(df)}行")
            return df

    except Exception as e:
        print(f"  真实特征矩阵系统不可用: {e}")

    # 回退到手动构建
    return _fallback_build(symbol, exchange, days, timeframe)


def _fallback_build(
    symbol: str = "BTCUSDT",
    exchange: str = "binance",
    days: int = 90,
    timeframe: str = "1h",
) -> pd.DataFrame:
    """回退方案：从FileDataLakeReader手动构建"""
    from infrastructure.storage.data_lake.file_reader import FileDataLakeReader

    reader = FileDataLakeReader()

    klines = _load_klines(reader, exchange, symbol, timeframe, days)
    funding = _safe_load(reader, reader.load_funding, exchange, symbol)
    oi = _safe_load(reader, reader.load_oi, exchange, symbol)
    trades = _safe_load(reader, reader.load_trades, exchange, symbol)

    return build_feature_matrix_from_df(
        klines, funding, oi, trades, timeframe
    )


def build_feature_matrix_from_df(
    klines: pd.DataFrame,
    funding: Optional[pd.DataFrame] = None,
    oi: Optional[pd.DataFrame] = None,
    trades: Optional[pd.DataFrame] = None,
    timeframe: str = "1h",
) -> pd.DataFrame:
    """从DataFrame手动构建特征矩阵"""

    df = klines[["timestamp", "open", "high", "low", "close", "volume"]].copy()
    df = df.sort_values("timestamp").reset_index(drop=True)

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    close = df["close"]

    # 基础收益
    df["ret_1"] = close.pct_change(1)
    df["ret_3"] = close.pct_change(3)
    df["ret_5"] = close.pct_change(5)
    df["ret_10"] = close.pct_change(10)
    df["ret_15"] = close.pct_change(15)
    df["ret_20"] = close.pct_change(20)
    df["ret_30"] = close.pct_change(30)
    df["ret_60"] = close.pct_change(60)
    df["change_pct"] = df["ret_1"]

    # 波动率
    bars_per_day = _timeframe_to_bars_per_day(timeframe)
    df["vol_20"] = df["ret_1"].rolling(20).std() * np.sqrt(bars_per_day * 252)
    df["vol_60"] = df["ret_1"].rolling(60).std() * np.sqrt(bars_per_day * 252)
    df["realized_vol"] = df["vol_60"]
    df["atr_14"] = (df["high"] - df["low"]).rolling(14).mean()
    df["atr"] = df["atr_14"]
    df["atr_pct"] = df["atr_14"] / close
    df["atr_expansion"] = df["atr_14"] / df["atr_14"].rolling(60).mean()

    # ZScore
    vol_ma = df["vol_20"].rolling(100).mean()
    vol_std = df["vol_20"].rolling(100).std()
    df["volatility_zscore"] = (df["vol_20"] - vol_ma) / vol_std.replace(0, np.nan)
    df["realized_vol_zscore"] = df["volatility_zscore"]

    vol_ma = df["volume"].rolling(100).mean()
    vol_std = df["volume"].rolling(100).std()
    df["volume_zscore"] = (df["volume"] - vol_ma) / vol_std.replace(0, np.nan)
    df["volume_ma"] = vol_ma
    df["volume_ratio"] = df["volume"] / vol_ma

    # 趋势
    df["trend_20"] = (close - close.rolling(20).mean()) / close.rolling(20).mean()
    df["trend_60"] = (close - close.rolling(60).mean()) / close.rolling(60).mean()
    df["slope"] = df["trend_20"]

    # 回撤与结构
    df["drawdown_from_high"] = (close - close.rolling(60).max()) / close.rolling(60).max()
    df["distance_from_high"] = df["drawdown_from_high"]
    df["new_high_60"] = (close >= close.rolling(60).max()).astype(float)
    df["new_high_20"] = (close >= close.rolling(20).max()).astype(float)
    df["new_low_60"] = (close <= close.rolling(60).min()).astype(float)

    # 抛物线
    df["parabolic_ret_10"] = np.exp(np.log(1 + df["ret_1"]).rolling(10).sum()) - 1
    p_ma = df["parabolic_ret_10"].rolling(100).mean()
    p_std = df["parabolic_ret_10"].rolling(100).std()
    df["parabolic_ret_zscore"] = (df["parabolic_ret_10"] - p_ma) / p_std.replace(0, np.nan)

    # K线形态
    df["range_pct"] = (df["high"] - df["low"]) / df["low"].replace(0, np.nan)
    df["upper_wick_pct"] = (df["high"] - np.maximum(df["open"], close)) / df["low"].replace(0, np.nan)
    df["lower_wick_pct"] = (np.minimum(df["open"], close) - df["low"]) / df["low"].replace(0, np.nan)
    df["body_pct"] = (close - df["open"]) / df["low"].replace(0, np.nan)

    # 连续涨跌
    df["is_up"] = (close > df["open"]).astype(float)
    df["is_down"] = (close < df["open"]).astype(float)
    df["consecutive_green"] = df["is_up"].groupby((~df["is_up"].astype(bool)).cumsum()).cumsum()
    df["consecutive_red"] = df["is_down"].groupby((~df["is_down"].astype(bool)).cumsum()).cumsum()

    # 波动率spike
    df["volatility_spike"] = df["volatility_zscore"]

    # 大量下跌
    df["high_volume_decline"] = ((df["ret_1"] < 0) & (df["volume_zscore"] > 1.5)).astype(float)

    # 附加特征用于可用性审计
    df["return_1h"] = df["ret_60"] if timeframe == "1m" else df["ret_1"]

    # Funding
    if funding is not None and len(funding) > 0:
        df = _merge_funding(df, funding)
    else:
        df["funding_rate"] = np.nan
        df["funding_zscore"] = np.nan

    df["funding_extreme_positive"] = (df["funding_zscore"] > 2).astype(float)

    # OI
    if oi is not None and len(oi) > 0:
        df = _merge_oi(df, oi)
    else:
        df["oi"] = np.nan
        df["oi_change_pct"] = np.nan
        df["oi_zscore"] = np.nan

    return df


# ========== 辅助函数 ==========

def _load_klines(
    reader, exchange: str, symbol: str, timeframe: str, days: int
) -> pd.DataFrame:
    klines = reader.load_klines(exchange, symbol, timeframe)

    if klines is None or len(klines) == 0:
        if timeframe != "1m":
            print(f"  {timeframe}数据不存在，从1m重采样...")
            klines_1m = reader.load_klines(exchange, symbol, "1m")
            if klines_1m is not None and len(klines_1m) > 0:
                klines = _resample_klines(klines_1m, timeframe)
            else:
                raise ValueError(f"没有1m数据作为fallback")
        else:
            raise ValueError(f"没有{timeframe} klines数据")

    klines["timestamp"] = pd.to_datetime(klines["timestamp"])
    cutoff = klines["timestamp"].max() - pd.Timedelta(days=days)
    klines = klines[klines["timestamp"] >= cutoff]

    return klines


def _safe_load(reader, load_fn, *args):
    try:
        df = load_fn(*args)
        if df is not None and len(df) > 0:
            df = df.copy()
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df
    except Exception:
        return None


def _merge_funding(df: pd.DataFrame, funding: pd.DataFrame) -> pd.DataFrame:
    df_ts = pd.to_datetime(df["timestamp"])
    fund_ts = pd.to_datetime(funding.get("funding_time", funding.get("timestamp", None)))

    if fund_ts is None:
        df["funding_rate"] = np.nan
        df["funding_zscore"] = np.nan
        return df

    fund = pd.DataFrame({
        "ts": fund_ts,
        "rate": pd.to_numeric(funding.get("funding_rate", funding.get("fundingRate", np.nan)), errors="coerce")
    }).dropna()

    if len(fund) == 0:
        df["funding_rate"] = np.nan
        df["funding_zscore"] = np.nan
        return df

    df_sorted = df.assign(_ts=df_ts).sort_values("_ts")
    fund_sorted = fund.sort_values("ts")

    merged = pd.merge_asof(
        df_sorted, fund_sorted, left_on="_ts", right_on="ts", direction="backward"
    )

    df["funding_rate"] = merged["rate"].values
    fr = df["funding_rate"]
    df["funding_zscore"] = (fr - fr.rolling(100).mean()) / fr.rolling(100).std().replace(0, np.nan)

    return df


def _merge_oi(df: pd.DataFrame, oi: pd.DataFrame) -> pd.DataFrame:
    df_ts = pd.to_datetime(df["timestamp"])

    if "timestamp" in oi.columns:
        oi_ts = pd.to_datetime(oi["timestamp"])
    else:
        oi_ts = pd.to_datetime(oi.get("open_interest_time", None))

    if oi_ts is None:
        df["oi"] = np.nan
        df["oi_change_pct"] = np.nan
        df["oi_zscore"] = np.nan
        return df

    oi_data = pd.DataFrame({
        "ts": oi_ts,
        "value": pd.to_numeric(oi.get("oi", oi.get("sumOpenInterest", oi.get("open_interest", np.nan))), errors="coerce")
    }).dropna()

    if len(oi_data) == 0:
        df["oi"] = np.nan
        df["oi_change_pct"] = np.nan
        df["oi_zscore"] = np.nan
        return df

    df_sorted = df.assign(_ts=df_ts).sort_values("_ts")
    oi_sorted = oi_data.sort_values("ts")

    merged = pd.merge_asof(
        df_sorted, oi_sorted, left_on="_ts", right_on="ts", direction="backward"
    )

    df["oi"] = merged["value"].values
    df["oi_change_pct"] = df["oi"].pct_change()
    oi_val = df["oi"]
    df["oi_zscore"] = (oi_val - oi_val.rolling(100).mean()) / oi_val.rolling(100).std().replace(0, np.nan)

    return df


def _resample_klines(df: pd.DataFrame, target: str) -> pd.DataFrame:
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.set_index("timestamp").sort_index()
    resampled = df.resample({
        "3m": "3min", "5m": "5min", "15m": "15min", "30m": "30min",
        "1h": "1h", "2h": "2h", "4h": "4h", "1d": "1D"
    }[target]).agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum"
    }).dropna(subset=["close"])

    return resampled.reset_index()


def _timeframe_to_ms(tf: str) -> int:
    ms_map = {
        "1m": 60000, "3m": 180000, "5m": 300000,
        "15m": 900000, "30m": 1800000, "1h": 3600000,
        "2h": 7200000, "4h": 14400000, "1d": 86400000
    }
    return ms_map.get(tf, 3600000)


def _timeframe_to_bars_per_day(tf: str) -> int:
    bars_map = {
        "1m": 1440, "3m": 480, "5m": 288,
        "15m": 96, "30m": 48, "1h": 24,
        "2h": 12, "4h": 6, "1d": 1
    }
    return bars_map.get(tf, 24)


__all__ = ["build_feature_matrix", "build_feature_matrix_from_df"]
