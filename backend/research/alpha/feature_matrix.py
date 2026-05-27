"""
Feature Matrix - 特征矩阵构建

从 parquet 原始数据（klines + funding）构建宽表。
不走 MarketContext，直接操作 DataFrame。

输出列：
  timestamp, open, high, low, close, volume,
  ret_1, ret_3, ret_5, ret_10,
  range_pct,
  vol_20, vol_60, volatility_zscore, atr_expansion,
  volume_zscore, trend_20, drawdown_from_high,
  funding_rate, funding_zscore
"""

import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


# ---------- 核心构建逻辑 ----------

def build_feature_matrix_from_df(
    klines_df: pd.DataFrame,
    funding_df: Optional[pd.DataFrame] = None,
    timeframe: str = "1m",
) -> pd.DataFrame:
    """
    从原始 DataFrame 构建特征矩阵。

    Args:
        klines_df: K 线数据，必须含 timestamp, open, high, low, close, volume
        funding_df: Funding 数据，含 timestamp, fundingRate（可为 None）
        timeframe: K 线周期 (用于年化波动率计算)

    Returns:
        特征矩阵 DataFrame，以 timestamp 排序
    """
    df = klines_df[["timestamp", "open", "high", "low", "close", "volume"]].copy()
    df = df.sort_values("timestamp").reset_index(drop=True)

    # 确保数值类型
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    close = df["close"]

    # --- 收益率 ---
    df["ret_1"] = close.pct_change(1)
    df["ret_3"] = close.pct_change(3)
    df["ret_5"] = close.pct_change(5)
    df["ret_10"] = close.pct_change(10)

    # --- K线实体范围 ---
    df["range_pct"] = (df["high"] - df["low"]) / df["low"].replace(0, np.nan)

    # --- 波动率 (年化, 根据 timeframe 自动计算) ---
    _BARS_PER_DAY = {"1m": 1440, "3m": 480, "5m": 288, "15m": 96,
                     "30m": 48, "1h": 24, "2h": 12, "4h": 6, "1d": 1}
    bars_per_day = _BARS_PER_DAY.get(timeframe, 96)
    bars_per_year = 252 * bars_per_day
    df["vol_20"] = df["ret_1"].rolling(20).std() * np.sqrt(bars_per_year)
    df["vol_60"] = df["ret_1"].rolling(60).std() * np.sqrt(bars_per_year)

    # --- 波动率 z-score ---
    vol20_ma = df["vol_20"].rolling(100).mean()
    vol20_std = df["vol_20"].rolling(100).std()
    df["volatility_zscore"] = (df["vol_20"] - vol20_ma) / vol20_std.replace(0, np.nan)

    # --- ATR expansion (ATR / ATR_ma) ---
    atr = df["range_pct"].rolling(14).mean()
    atr_ma = atr.rolling(60).mean()
    df["atr_expansion"] = atr / atr_ma.replace(0, np.nan)

    # --- 成交量 z-score ---
    vol_ma = df["volume"].rolling(100).mean()
    vol_std = df["volume"].rolling(100).std()
    df["volume_zscore"] = (df["volume"] - vol_ma) / vol_std.replace(0, np.nan)

    # --- 趋势 (close 偏离 20-bar 均线的百分比) ---
    ma_20 = close.rolling(20).mean()
    df["trend_20"] = (close - ma_20) / ma_20.replace(0, np.nan)

    # --- 从高点回撤 ---
    rolling_high = close.rolling(60, min_periods=1).max()
    df["drawdown_from_high"] = (close - rolling_high) / rolling_high.replace(0, np.nan)

    # --- Funding ---
    if funding_df is not None and len(funding_df) > 0:
        df = _merge_funding(df, funding_df)
    else:
        df["funding_rate"] = np.nan
        df["funding_zscore"] = np.nan

    return df


def _merge_funding(df: pd.DataFrame, funding_df: pd.DataFrame) -> pd.DataFrame:
    """将 funding 数据 forward-fill 到 klines 时间轴上。"""
    fund = funding_df.copy()

    # 确保 timestamp 列存在
    if "timestamp" not in fund.columns:
        # 尝试用 index
        fund = fund.reset_index()

    # 处理 fundingRate 可能为 string 的情况
    if "fundingRate" in fund.columns:
        fund["funding_rate"] = pd.to_numeric(fund["fundingRate"], errors="coerce")
    elif "funding_rate" in fund.columns:
        fund["funding_rate"] = pd.to_numeric(fund["funding_rate"], errors="coerce")
    else:
        df["funding_rate"] = np.nan
        df["funding_zscore"] = np.nan
        return df

    fund = fund[["timestamp", "funding_rate"]].copy()
    fund["timestamp"] = pd.to_datetime(fund["timestamp"])

    # klines timestamp 也转 datetime
    df_ts = df["timestamp"].copy()
    if not pd.api.types.is_datetime64_any_dtype(df_ts):
        df_ts = pd.to_datetime(df_ts)

    # merge_asof: 对每个 kline bar，取最近一条 funding 记录
    df_sorted = df.assign(_ts=df_ts).sort_values("_ts")
    fund_sorted = fund.sort_values("timestamp")

    merged = pd.merge_asof(
        df_sorted,
        fund_sorted,
        left_on="_ts",
        right_on="timestamp",
        suffixes=("", "_fund"),
    )

    df["funding_rate"] = merged["funding_rate"].values

    # funding z-score (rolling 100-bar)
    fr = df["funding_rate"]
    df["funding_zscore"] = (fr - fr.rolling(100).mean()) / fr.rolling(100).std().replace(0, np.nan)

    return df


# ---------- 便捷加载接口 ----------

def _resample_klines(klines_df: pd.DataFrame, target_timeframe: str) -> pd.DataFrame:
    """将 1m klines 重采样到目标 timeframe。"""
    tf_map = {"5m": "5min", "15m": "15min", "30m": "30min",
              "1h": "1h", "2h": "2h", "4h": "4h", "1d": "1D"}
    freq = tf_map.get(target_timeframe)
    if freq is None:
        raise ValueError(f"不支持的重采样目标: {target_timeframe}")

    df = klines_df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.set_index("timestamp").sort_index()
    resampled = df.resample(freq).agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).dropna(subset=["close"])

    resampled = resampled.reset_index()
    return resampled


def build_feature_matrix(
    symbol: str = "BTCUSDT",
    exchange: str = "binance",
    days: int = 90,
    timeframe: str = "1m",
) -> pd.DataFrame:
    """
    从数据湖加载并构建特征矩阵。

    Args:
        symbol: 交易对
        exchange: 交易所
        days: 回看天数
        timeframe: K 线周期

    Returns:
        特征矩阵 DataFrame
    """
    from infrastructure.storage.data_lake.file_reader import FileDataLakeReader

    reader = FileDataLakeReader()

    # 加载 klines (如果目标 timeframe 不存在, fallback 到 1m 并重采样)
    klines_df = reader.load_klines(
        exchange=exchange,
        symbol=symbol,
        timeframe=timeframe,
    )

    if klines_df is None or len(klines_df) == 0:
        if timeframe != "1m":
            print(f"  {timeframe} 数据不存在, 从 1m 重采样...")
            klines_1m = reader.load_klines(
                exchange=exchange, symbol=symbol, timeframe="1m",
            )
            if klines_1m is not None and len(klines_1m) > 0:
                klines_df = _resample_klines(klines_1m, timeframe)
            else:
                raise ValueError(f"无 klines 数据: {exchange}/{symbol}/1m (fallback)")
        else:
            raise ValueError(f"无 klines 数据: {exchange}/{symbol}/{timeframe}")

    # 按天数裁剪
    if "timestamp" in klines_df.columns:
        ts = pd.to_datetime(klines_df["timestamp"])
        cutoff = ts.max() - pd.Timedelta(days=days)
        klines_df = klines_df[ts >= cutoff].copy()

    # 加载 funding
    try:
        funding_df = reader.load_funding(exchange=exchange, symbol=symbol)
    except Exception:
        funding_df = None

    return build_feature_matrix_from_df(klines_df, funding_df, timeframe=timeframe)


__all__ = ["build_feature_matrix", "build_feature_matrix_from_df"]
