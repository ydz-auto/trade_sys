"""
Funding Data Loader - 从 FileDataLakeReader 加载 funding 数据并合并到特征矩阵

复用 research 中 _merge_funding 的逻辑，但作为独立模块供 FeatureEngine 使用。
"""

import sys
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def load_funding_data(exchange: str, symbol: str) -> Optional[pd.DataFrame]:
    """从 FileDataLakeReader 加载 funding 数据

    Args:
        exchange: 交易所
        symbol: 交易对

    Returns:
        funding DataFrame 或 None
    """
    try:
        from infrastructure.storage.data_lake.file_reader import FileDataLakeReader
        reader = FileDataLakeReader()
        funding = reader.load_funding(exchange, symbol)
        if funding is not None and len(funding) > 0:
            return funding.copy()
        return None
    except Exception:
        return None


def merge_funding_into_df(
    df: pd.DataFrame,
    funding: Optional[pd.DataFrame] = None,
    exchange: str = "binance",
    symbol: str = "BTCUSDT",
) -> pd.DataFrame:
    """将 funding 数据合并到特征矩阵

    如果 funding 为 None，会尝试从 FileDataLakeReader 加载。
    合并逻辑与 research 中 _merge_funding 完全一致。

    Args:
        df: 特征矩阵 DataFrame（必须包含 timestamp 列）
        funding: funding 数据，如果为 None 则自动加载
        exchange: 交易所
        symbol: 交易对

    Returns:
        包含 funding_rate, funding_zscore, funding_extreme_positive 的 DataFrame
    """
    if funding is None:
        funding = load_funding_data(exchange, symbol)

    if funding is None or len(funding) == 0:
        df["funding_rate"] = np.nan
        df["funding_zscore"] = np.nan
        df["funding_extreme_positive"] = np.nan
        return df

    df_ts = pd.to_datetime(df["timestamp"])
    fund_ts = pd.to_datetime(funding.get("funding_time", funding.get("timestamp", None)))

    if fund_ts is None:
        df["funding_rate"] = np.nan
        df["funding_zscore"] = np.nan
        df["funding_extreme_positive"] = np.nan
        return df

    fund = pd.DataFrame({
        "ts": fund_ts,
        "rate": pd.to_numeric(
            funding.get("funding_rate", funding.get("fundingRate", np.nan)),
            errors="coerce"
        )
    }).dropna()

    if len(fund) == 0:
        df["funding_rate"] = np.nan
        df["funding_zscore"] = np.nan
        df["funding_extreme_positive"] = np.nan
        return df

    df_sorted = df.assign(_ts=df_ts).sort_values("_ts")
    fund_sorted = fund.sort_values("ts")

    merged = pd.merge_asof(
        df_sorted, fund_sorted, left_on="_ts", right_on="ts", direction="backward"
    )

    fr = merged["rate"].values
    fr_series = pd.Series(fr, index=df.index)
    fr_zscore = (fr_series - fr_series.rolling(100).mean()) / fr_series.rolling(100).std().replace(0, np.nan)

    new_cols = pd.DataFrame({
        "funding_rate": fr,
        "funding_zscore": fr_zscore.values,
        "funding_extreme_positive": (fr_zscore > 2).astype(float).values,
    }, index=df.index)

    for col in ["funding_rate", "funding_zscore", "funding_extreme_positive"]:
        if col in df.columns:
            df.drop(columns=[col], inplace=True, errors="ignore")

    df = pd.concat([df, new_cols], axis=1)

    return df
