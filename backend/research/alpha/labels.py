"""
Alpha Labels - 未来收益标签

计算每个 bar 的未来收益、MFE（最大有利偏移）、MAE（最大不利偏移）。

用途：与 feature_matrix 配合，做 IC 分析。
"""

from typing import List
import numpy as np
import pandas as pd


def compute_labels(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    horizons: List[int] = None,
    mfe_mae_window: int = 10,
) -> pd.DataFrame:
    """
    计算未来收益标签。

    Args:
        close: 收盘价序列
        high: 最高价序列
        low: 最低价序列
        horizons: 未来收益的 bar 数列表，默认 [1, 3, 5, 10]
        mfe_mae_window: MFE/MAE 的回望窗口

    Returns:
        pd.DataFrame，index 对齐输入，列：
        - future_ret_{h}: (close[i+h] - close[i]) / close[i]
        - future_mfe_{w}: (max(high[i+1:i+w+1]) - close[i]) / close[i]
        - future_mae_{w}: (min(low[i+1:i+w+1]) - close[i]) / close[i]
    """
    if horizons is None:
        horizons = [1, 3, 5, 10]

    n = len(close)
    result = pd.DataFrame(index=range(n))

    # 未来收益
    for h in horizons:
        col = f"future_ret_{h}"
        future_ret = np.full(n, np.nan)
        if h < n:
            future_ret[: n - h] = (close[h:] - close[: n - h]) / close[: n - h]
        result[col] = future_ret

    # MFE: 未来 w bars 内最高价相对当前 close 的收益
    w = mfe_mae_window
    mfe_col = f"future_mfe_{w}"
    mae_col = f"future_mae_{w}"
    mfe = np.full(n, np.nan)
    mae = np.full(n, np.nan)

    for i in range(n - w):
        window_high = np.max(high[i + 1 : i + w + 1])
        window_low = np.min(low[i + 1 : i + w + 1])
        mfe[i] = (window_high - close[i]) / close[i]
        mae[i] = (window_low - close[i]) / close[i]

    result[mfe_col] = mfe
    result[mae_col] = mae

    return result


def compute_labels_from_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    从 DataFrame 计算标签（便捷接口）。

    Args:
        df: 必须包含 close, high, low 列

    Returns:
        标签 DataFrame，index 与 df 对齐
    """
    labels = compute_labels(
        close=df["close"].values,
        high=df["high"].values,
        low=df["low"].values,
    )
    labels.index = df.index
    return labels


__all__ = ["compute_labels", "compute_labels_from_df"]
