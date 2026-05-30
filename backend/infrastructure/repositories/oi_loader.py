"""
OI Data Loader - 从 FileDataLakeReader 加载 OI 数据并合并到特征矩阵

与 funding_loader.py 对称设计，计算 OI 衍生特征：
  - oi: 原始持仓量
  - oi_zscore: 滚动 z-score
  - oi_change: OI 变化率
  - oi_funding_divergence: OI 增加 + Funding 极端的背离指标
  - leverage_crowdedness: 杠杆拥挤度
"""

import sys
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def load_oi_data(exchange: str, symbol: str) -> Optional[pd.DataFrame]:
    try:
        from infrastructure.storage.data_lake.file_reader import FileDataLakeReader
        reader = FileDataLakeReader()
        oi = reader.load_oi(exchange, symbol)
        if oi is not None and len(oi) > 0:
            return oi.copy()
        return None
    except Exception:
        return None


def merge_oi_into_df(
    df: pd.DataFrame,
    oi: Optional[pd.DataFrame] = None,
    exchange: str = "binance",
    symbol: str = "BTCUSDT",
    oi_window: int = 100,
) -> pd.DataFrame:
    """
    将 OI 数据合并到特征矩阵并计算衍生特征。

    Args:
        df: 特征矩阵 DataFrame（必须包含 timestamp 列）
        oi: OI 数据，如果为 None 则自动加载
        exchange: 交易所
        symbol: 交易对
        oi_window: 滚动窗口大小

    Returns:
        包含 oi, oi_zscore, oi_change, oi_funding_divergence, leverage_crowdedness 的 DataFrame
    """
    if oi is None:
        oi = load_oi_data(exchange, symbol)

    if oi is None or len(oi) == 0:
        df["oi"] = np.nan
        df["oi_zscore"] = np.nan
        df["oi_change"] = np.nan
        df["oi_funding_divergence"] = np.nan
        df["leverage_crowdedness"] = np.nan
        return df

    df_ts = pd.to_datetime(df["timestamp"])

    oi_col = None
    for col_name in ["sumOpenInterest", "sumOpenInterestValue", "openInterest", "oi"]:
        if col_name in oi.columns:
            oi_col = col_name
            break

    if oi_col is None:
        df["oi"] = np.nan
        df["oi_zscore"] = np.nan
        df["oi_change"] = np.nan
        df["oi_funding_divergence"] = np.nan
        df["leverage_crowdedness"] = np.nan
        return df

    oi_ts = pd.to_datetime(oi["timestamp"])

    oi_clean = pd.DataFrame({
        "ts": oi_ts,
        "oi_val": pd.to_numeric(oi[oi_col], errors="coerce"),
    }).dropna()

    if len(oi_clean) == 0:
        df["oi"] = np.nan
        df["oi_zscore"] = np.nan
        df["oi_change"] = np.nan
        df["oi_funding_divergence"] = np.nan
        df["leverage_crowdedness"] = np.nan
        return df

    df_sorted = df.assign(_ts=df_ts).sort_values("_ts")
    oi_sorted = oi_clean.sort_values("ts")

    merged = pd.merge_asof(
        df_sorted, oi_sorted, left_on="_ts", right_on="ts", direction="backward"
    )

    oi_vals = merged["oi_val"].values
    oi_series = pd.Series(oi_vals, index=df.index)

    oi_mean = oi_series.rolling(oi_window, min_periods=20).mean()
    oi_std = oi_series.rolling(oi_window, min_periods=20).std().replace(0, np.nan)
    oi_zscore = ((oi_series - oi_mean) / oi_std).values

    oi_prev = oi_series.shift(1)
    oi_change = ((oi_series - oi_prev) / oi_prev.abs().replace(0, np.nan)).values

    if "funding_zscore" in df.columns:
        fz = df["funding_zscore"].values.astype(float)
        oi_funding_divergence = np.where(
            np.isnan(oi_zscore) | np.isnan(fz),
            np.nan,
            oi_zscore * np.abs(fz),
        )
    else:
        oi_funding_divergence = np.full(len(df), np.nan)

    leverage_crowdedness = np.where(
        np.isnan(oi_zscore),
        np.nan,
        np.minimum(1.0, (np.abs(oi_zscore) + (
            np.abs(df["funding_zscore"].values.astype(float))
            if "funding_zscore" in df.columns
            else np.zeros(len(df))
        )) / 4.0),
    )

    new_cols = pd.DataFrame({
        "oi": oi_vals,
        "oi_zscore": oi_zscore,
        "oi_change": oi_change,
        "oi_funding_divergence": oi_funding_divergence,
        "leverage_crowdedness": leverage_crowdedness,
    }, index=df.index)

    for col in new_cols.columns:
        if col in df.columns:
            df.drop(columns=[col], inplace=True, errors="ignore")

    df = pd.concat([df, new_cols], axis=1)

    return df
