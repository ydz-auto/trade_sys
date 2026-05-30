"""
Alpha Hierarchical Clustering

基于相关性矩阵对 Alpha 进行层次聚类，识别 Alpha 家族。

核心逻辑：
  1. 距离 = 1 - |corr|
  2. Ward / average linkage 层次聚类
  3. 按距离阈值切割，得到 Alpha 家族
"""

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from infrastructure.logging import get_logger

logger = get_logger("research.alpha.correlation.cluster")


def cluster_alphas(
    corr_matrix: pd.DataFrame,
    distance_threshold: float = 0.3,
    linkage_method: str = "average",
) -> Dict[str, List[str]]:
    """
    对 Alpha 进行层次聚类。

    Args:
        corr_matrix: Pearson 相关系数矩阵
        distance_threshold: 聚类切割距离阈值 (1 - |corr| < threshold 视为同族)
                           0.3 意味着 |corr| > 0.7 的归为同族
        linkage_method: 聚类链接方法 (average, ward, complete, single)

    Returns:
        {cluster_name: [alpha_1, alpha_2, ...]}
    """
    try:
        from scipy.cluster.hierarchy import linkage, fcluster
        from scipy.spatial.distance import squareform
    except ImportError:
        logger.error("scipy is required for clustering. Install with: pip install scipy")
        return _fallback_cluster(corr_matrix, distance_threshold)

    alphas = corr_matrix.columns.tolist()
    if len(alphas) < 2:
        return {"cluster_0": alphas}

    abs_corr = corr_matrix.abs().values.copy()
    np.fill_diagonal(abs_corr, 1.0)

    distance_matrix = 1.0 - abs_corr
    np.fill_diagonal(distance_matrix, 0.0)

    distance_matrix = np.maximum(distance_matrix, 0.0)

    condensed = squareform(distance_matrix, checks=False)

    Z = linkage(condensed, method=linkage_method)

    labels = fcluster(Z, t=distance_threshold, criterion="distance")

    clusters: Dict[str, List[str]] = {}
    for idx, label in enumerate(labels):
        cluster_name = f"cluster_{label}"
        if cluster_name not in clusters:
            clusters[cluster_name] = []
        clusters[cluster_name].append(alphas[idx])

    logger.info(
        f"Clustering: {len(alphas)} alphas -> {len(clusters)} clusters "
        f"(threshold={distance_threshold}, method={linkage_method})"
    )

    return clusters


def _fallback_cluster(
    corr_matrix: pd.DataFrame,
    distance_threshold: float,
) -> Dict[str, List[str]]:
    alphas = corr_matrix.columns.tolist()
    corr_threshold = 1.0 - distance_threshold

    visited = set()
    clusters: Dict[str, List[str]] = {}
    cluster_id = 0

    for alpha in alphas:
        if alpha in visited:
            continue

        members = [alpha]
        visited.add(alpha)

        for other in alphas:
            if other in visited:
                continue
            if alpha in corr_matrix.columns and other in corr_matrix.columns:
                val = corr_matrix.loc[alpha, other]
                if not np.isnan(val) and abs(val) > corr_threshold:
                    members.append(other)
                    visited.add(other)

        clusters[f"cluster_{cluster_id}"] = members
        cluster_id += 1

    return clusters


def get_dendrogram_data(
    corr_matrix: pd.DataFrame,
    linkage_method: str = "average",
) -> Optional[object]:
    """
    获取层次聚类的 linkage 矩阵，用于绘制 dendrogram。

    Returns:
        scipy linkage matrix, or None if scipy not available
    """
    try:
        from scipy.cluster.hierarchy import linkage
        from scipy.spatial.distance import squareform
    except ImportError:
        logger.warning("scipy not available, cannot compute dendrogram")
        return None

    abs_corr = corr_matrix.abs().values.copy()
    np.fill_diagonal(abs_corr, 1.0)
    distance_matrix = 1.0 - abs_corr
    np.fill_diagonal(distance_matrix, 0.0)
    distance_matrix = np.maximum(distance_matrix, 0.0)

    condensed = squareform(distance_matrix, checks=False)
    return linkage(condensed, method=linkage_method)
