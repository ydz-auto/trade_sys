"""
Alpha Correlation Report Generator

统一输出所有 Phase 的分析结果。

输出：
  1. 终端文本报告
  2. CSV 文件（相关性矩阵、聚类结果、独立 Alpha）
"""

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from infrastructure.logging import get_logger

logger = get_logger("research.alpha.correlation.report")


def generate_correlation_report(
    return_matrix: pd.DataFrame,
    corr_matrix: pd.DataFrame,
    clusters: Dict[str, List[str]],
    independent_result: Dict,
    family_matches: List[Dict],
    symbol: str = "",
    corr_threshold: float = 0.7,
) -> str:
    lines = []

    lines.append("=" * 70)
    header = "Alpha Correlation Analysis"
    if symbol:
        header += f" | {symbol}"
    lines.append(header)
    lines.append("=" * 70)

    lines.append("")
    lines.append("SUMMARY")
    lines.append("-" * 40)
    total = independent_result.get("total_alphas", 0)
    independent = independent_result.get("independent_alpha_count", 0)
    lines.append(f"  Total Alpha Strategies:    {total}")
    lines.append(f"  Independent Alpha Sources: {independent}")
    lines.append(f"  Correlation Threshold:     {corr_threshold}")
    lines.append(f"  Reduction Ratio:           {independent / total:.1%}" if total > 0 else "  Reduction Ratio:           N/A")

    lines.append("")
    lines.append("INDEPENDENT ALPHA GROUPS")
    lines.append("-" * 40)
    for group in independent_result.get("groups", []):
        rep = group["representative"]
        members = group["members"]
        size = group["size"]
        mean_corr = group["mean_internal_corr"]
        lines.append(f"  [{rep}] (size={size}, mean_internal_corr={mean_corr:.2f})")
        for m in members:
            tag = " <-- representative" if m == rep else ""
            lines.append(f"    - {m}{tag}")

    lines.append("")
    lines.append("CLUSTER -> FAMILY MATCH")
    lines.append("-" * 40)
    for match in family_matches:
        cluster = match["cluster"]
        best = match["best_family_match"]
        ratio = match["match_ratio"]
        members = match["members"]
        lines.append(f"  {cluster} -> {best} (match={ratio:.0%})")
        for m in members:
            lines.append(f"    - {m}")

    lines.append("")
    lines.append("CORRELATION MATRIX (top pairs)")
    lines.append("-" * 40)
    _append_top_corr_pairs(lines, corr_matrix, top_n=15)

    lines.append("")
    lines.append("ALPHA PORTFOLIO (one per group)")
    lines.append("-" * 40)
    for group in independent_result.get("groups", []):
        rep = group["representative"]
        lines.append(f"  {rep}")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def _append_top_corr_pairs(
    lines: List[str],
    corr_matrix: pd.DataFrame,
    top_n: int = 15,
) -> None:
    alphas = corr_matrix.columns.tolist()
    pairs = []

    for i in range(len(alphas)):
        for j in range(i + 1, len(alphas)):
            val = corr_matrix.iloc[i, j]
            if not np.isnan(val):
                pairs.append((alphas[i], alphas[j], val, abs(val)))

    pairs.sort(key=lambda x: x[3], reverse=True)

    for alpha_1, alpha_2, corr, abs_corr in pairs[:top_n]:
        lines.append(f"  {alpha_1:<30} {alpha_2:<30} corr={corr:+.3f}")


def save_correlation_csv(
    corr_matrix: pd.DataFrame,
    output_dir: str,
    symbol: str = "",
) -> None:
    from pathlib import Path
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    prefix = f"{symbol}_" if symbol else ""

    corr_matrix.to_csv(out / f"{prefix}alpha_correlation.csv")

    abs_corr = corr_matrix.abs()
    abs_corr.to_csv(out / f"{prefix}alpha_abs_correlation.csv")

    logger.info(f"Correlation CSVs saved to {out}")


def save_cluster_csv(
    clusters: Dict[str, List[str]],
    independent_result: Dict,
    output_dir: str,
    symbol: str = "",
) -> None:
    from pathlib import Path
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    prefix = f"{symbol}_" if symbol else ""

    rows = []
    for group in independent_result.get("groups", []):
        for member in group["members"]:
            rows.append({
                "group_representative": group["representative"],
                "alpha_name": member,
                "group_size": group["size"],
                "mean_internal_corr": group["mean_internal_corr"],
                "is_representative": member == group["representative"],
            })

    df = pd.DataFrame(rows)
    df.to_csv(out / f"{prefix}alpha_clusters.csv", index=False)

    logger.info(f"Cluster CSV saved to {out}")
