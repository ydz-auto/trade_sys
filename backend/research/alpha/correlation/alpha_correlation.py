"""
Alpha Correlation Matrix

基于真实策略收益序列计算 Alpha 之间的相关性矩阵。

核心逻辑：
  1. 输入 AlphaReturnMatrixBuilder 生成的收益 DataFrame
  2. 计算 Pearson 相关系数矩阵
  3. 输出相关性矩阵 + 绝对值相关性矩阵
"""

from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

from infrastructure.logging import get_logger

logger = get_logger("research.alpha.correlation.correlation")


def compute_alpha_correlation(
    return_matrix: pd.DataFrame,
    min_trades: int = 10,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    计算 Alpha 收益相关性矩阵。

    Args:
        return_matrix: AlphaReturnMatrixBuilder 输出的收益矩阵
                       index=timestamp, columns=alpha_name, values=per-bar return
        min_trades: 最少交易次数过滤（非零收益的 bar 数）

    Returns:
        corr_matrix: Pearson 相关系数矩阵
        abs_corr_matrix: 绝对值相关系数矩阵
    """
    nonzero_counts = (return_matrix != 0).sum()
    valid_alphas = nonzero_counts[nonzero_counts >= min_trades].index.tolist()

    if len(valid_alphas) < 2:
        logger.warning(
            f"Only {len(valid_alphas)} alphas with >= {min_trades} trades, "
            f"cannot compute correlation"
        )
        empty = pd.DataFrame()
        return empty, empty

    filtered = return_matrix[valid_alphas]

    corr_matrix = filtered.corr(method="pearson")

    abs_corr_matrix = corr_matrix.abs()

    logger.info(
        f"Correlation matrix: {len(valid_alphas)} alphas, "
        f"mean abs corr = {abs_corr_matrix.values[np.triu_indices_from(abs_corr_matrix.values, k=1)].mean():.3f}"
    )

    return corr_matrix, abs_corr_matrix


def find_highly_correlated_pairs(
    corr_matrix: pd.DataFrame,
    threshold: float = 0.7,
) -> pd.DataFrame:
    """
    找出相关性超过阈值的 Alpha 对。

    Returns:
        DataFrame with columns: [alpha_1, alpha_2, correlation]
    """
    alphas = corr_matrix.columns.tolist()
    pairs = []

    for i in range(len(alphas)):
        for j in range(i + 1, len(alphas)):
            val = corr_matrix.iloc[i, j]
            if not np.isnan(val) and abs(val) > threshold:
                pairs.append({
                    "alpha_1": alphas[i],
                    "alpha_2": alphas[j],
                    "correlation": round(val, 4),
                    "abs_correlation": round(abs(val), 4),
                })

    if not pairs:
        return pd.DataFrame(columns=["alpha_1", "alpha_2", "correlation", "abs_correlation"])

    df = pd.DataFrame(pairs)
    df = df.sort_values("abs_correlation", ascending=False).reset_index(drop=True)
    return df
