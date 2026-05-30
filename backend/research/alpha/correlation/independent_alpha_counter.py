"""
Independent Alpha Counter

基于相关性阈值计算真正独立的 Alpha 数量。

核心逻辑：
  如果两个 Alpha 的 |corr| > threshold，视为同一个 Alpha Source。
  用 Union-Find 计算独立 Alpha 数量。
"""

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from infrastructure.logging import get_logger

logger = get_logger("research.alpha.correlation.independent_counter")


class UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x: int, y: int) -> None:
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return
        if self.rank[rx] < self.rank[ry]:
            rx, ry = ry, rx
        self.parent[ry] = rx
        if self.rank[rx] == self.rank[ry]:
            self.rank[rx] += 1


def count_independent_alphas(
    corr_matrix: pd.DataFrame,
    corr_threshold: float = 0.7,
) -> Dict:
    """
    计算独立 Alpha 数量。

    Args:
        corr_matrix: Pearson 相关系数矩阵
        corr_threshold: |corr| > threshold 视为同 Alpha

    Returns:
        {
            "total_alphas": 17,
            "independent_alpha_count": 4,
            "corr_threshold": 0.7,
            "groups": [
                {
                    "representative": "ret_5_reversal",
                    "members": ["ret_1_reversal", "ret_3_reversal", ...],
                    "mean_internal_corr": 0.92,
                    "size": 5,
                },
                ...
            ]
        }
    """
    alphas = corr_matrix.columns.tolist()
    n = len(alphas)

    if n == 0:
        return {
            "total_alphas": 0,
            "independent_alpha_count": 0,
            "corr_threshold": corr_threshold,
            "groups": [],
        }

    uf = UnionFind(n)

    for i in range(n):
        for j in range(i + 1, n):
            val = corr_matrix.iloc[i, j]
            if not np.isnan(val) and abs(val) > corr_threshold:
                uf.union(i, j)

    group_map: Dict[int, List[int]] = {}
    for i in range(n):
        root = uf.find(i)
        if root not in group_map:
            group_map[root] = []
        group_map[root].append(i)

    groups = []
    for root, indices in group_map.items():
        members = [alphas[i] for i in indices]

        representative = _pick_representative(corr_matrix, alphas, indices)

        mean_internal_corr = _compute_mean_internal_corr(
            corr_matrix, alphas, indices
        )

        groups.append({
            "representative": representative,
            "members": members,
            "mean_internal_corr": round(mean_internal_corr, 4),
            "size": len(members),
        })

    groups.sort(key=lambda g: g["size"], reverse=True)

    result = {
        "total_alphas": n,
        "independent_alpha_count": len(groups),
        "corr_threshold": corr_threshold,
        "groups": groups,
    }

    logger.info(
        f"Independent Alpha: {n} total -> {len(groups)} independent "
        f"(threshold={corr_threshold})"
    )

    return result


def _pick_representative(
    corr_matrix: pd.DataFrame,
    alphas: List[str],
    indices: List[int],
) -> str:
    """
    选择组内与其他成员平均相关性最高的 Alpha 作为代表。
    """
    if len(indices) == 1:
        return alphas[indices[0]]

    best_alpha = alphas[indices[0]]
    best_mean_corr = -1.0

    for i in indices:
        corrs = []
        for j in indices:
            if i == j:
                continue
            val = corr_matrix.iloc[i, j]
            if not np.isnan(val):
                corrs.append(abs(val))
        mean_corr = np.mean(corrs) if corrs else 0.0
        if mean_corr > best_mean_corr:
            best_mean_corr = mean_corr
            best_alpha = alphas[i]

    return best_alpha


def _compute_mean_internal_corr(
    corr_matrix: pd.DataFrame,
    alphas: List[str],
    indices: List[int],
) -> float:
    if len(indices) < 2:
        return 1.0

    corrs = []
    for ii, i in enumerate(indices):
        for j in indices[ii + 1:]:
            val = corr_matrix.iloc[i, j]
            if not np.isnan(val):
                corrs.append(abs(val))

    return float(np.mean(corrs)) if corrs else 0.0
