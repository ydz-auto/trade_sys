"""
IC Analysis - 信息系数分析

计算 feature 与 future return 的 IC（Pearson）和 Rank IC（Spearman）。
支持按 regime 分组计算条件 IC。

核心输出表格:
  feature, horizon, ic, rank_ic, p_value, sample_count

CLI:
  python -m research.alpha.ic_analysis --symbol BTCUSDT --days 90
  python -m research.alpha.ic_analysis --symbol BTCUSDT --days 90 --output reports/alpha/ic_btcusdt_90d.csv
"""

import sys
import os
from pathlib import Path
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse

import numpy as np
import pandas as pd
from scipy import stats

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


# ---------- 默认配置 ----------

DEFAULT_FEATURES = [
    "funding_rate",
    "funding_zscore",
    "volume_zscore",
    "vol_20",
    "vol_60",
    "trend_20",
    "ret_1",
    "ret_5",
    "ret_10",
]

DEFAULT_LABELS = [
    "future_ret_1",
    "future_ret_3",
    "future_ret_5",
    "future_ret_10",
]


# ---------- IC 计算 ----------

def _compute_single_ic(
    feature_vals: np.ndarray,
    label_vals: np.ndarray,
) -> dict:
    """计算单对 feature-label 的 IC 统计。"""
    mask = ~(np.isnan(feature_vals) | np.isnan(label_vals))
    f = feature_vals[mask]
    l = label_vals[mask]
    n = len(f)

    if n < 30:
        return {
            "ic": np.nan, "rank_ic": np.nan,
            "p_value": np.nan, "rank_p_value": np.nan,
            "sample_count": n,
        }

    # Pearson IC
    ic, p_val = stats.pearsonr(f, l)

    # Spearman Rank IC
    rank_ic, rank_p = stats.spearmanr(f, l)

    return {
        "ic": ic,
        "rank_ic": rank_ic,
        "p_value": p_val,
        "rank_p_value": rank_p,
        "sample_count": n,
    }


def compute_ic_table(
    feature_matrix: pd.DataFrame,
    label_df: pd.DataFrame,
    features: Optional[List[str]] = None,
    labels: Optional[List[str]] = None,
    max_workers: Optional[int] = None,
) -> pd.DataFrame:
    """
    计算 feature × label 的 IC 表格。

    Args:
        feature_matrix: 特征矩阵
        label_df: 标签 DataFrame（index 需与 feature_matrix 对齐）
        features: 要分析的特征列名列表
        labels: 要分析的标签列名列表
        max_workers: 线程数（默认 CPU 核心数）

    Returns:
        IC 表格 DataFrame
    """
    if features is None:
        features = [c for c in DEFAULT_FEATURES if c in feature_matrix.columns]
    if labels is None:
        labels = [c for c in DEFAULT_LABELS if c in label_df.columns]

    # 对齐 index
    common_idx = feature_matrix.index.intersection(label_df.index)
    fm = feature_matrix.loc[common_idx]
    lb = label_df.loc[common_idx]

    tasks = []
    for feat in features:
        if feat not in fm.columns:
            continue
        for lab in labels:
            if lab not in lb.columns:
                continue
            tasks.append((feat, lab))

    def _worker(feat, lab):
        f_vals = fm[feat].values.astype(float)
        l_vals = lb[lab].values.astype(float)
        result = _compute_single_ic(f_vals, l_vals)
        result["feature"] = feat
        result["label"] = lab
        # 提取 horizon 数字
        result["horizon"] = int(lab.replace("future_ret_", "")) if "future_ret_" in lab else 0
        return result

    rows = []
    if max_workers is None:
        max_workers = min(os.cpu_count() or 4, 8)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_worker, feat, lab): (feat, lab)
            for feat, lab in tasks
        }
        for future in as_completed(futures):
            rows.append(future.result())

    result_df = pd.DataFrame(rows)
    if len(result_df) > 0:
        result_df = result_df.sort_values(["feature", "horizon"]).reset_index(drop=True)
        # 调整列顺序
        cols = ["feature", "label", "horizon", "ic", "rank_ic", "p_value", "rank_p_value", "sample_count"]
        result_df = result_df[[c for c in cols if c in result_df.columns]]

    return result_df


def compute_conditional_ic(
    feature_matrix: pd.DataFrame,
    label_df: pd.DataFrame,
    feature: str,
    label: str,
    regime_col: str = "trend_regime",
    max_workers: Optional[int] = None,
) -> pd.DataFrame:
    """
    按 regime 分组计算条件 IC。

    Returns:
        每个 regime 的 IC 统计
    """
    if regime_col not in feature_matrix.columns:
        raise ValueError(f"feature_matrix 中无 {regime_col} 列，需先调用 classify_regime()")

    common_idx = feature_matrix.index.intersection(label_df.index)
    fm = feature_matrix.loc[common_idx]
    lb = label_df.loc[common_idx]

    regimes = fm[regime_col].unique()
    rows = []

    def _worker(regime):
        mask = fm[regime_col] == regime
        f_vals = fm.loc[mask, feature].values.astype(float)
        l_vals = lb.loc[mask, label].values.astype(float)
        result = _compute_single_ic(f_vals, l_vals)
        result["regime"] = regime
        result["feature"] = feature
        result["label"] = label
        return result

    with ThreadPoolExecutor(max_workers=max_workers or 4) as executor:
        futures = {executor.submit(_worker, r): r for r in regimes}
        for future in as_completed(futures):
            rows.append(future.result())

    return pd.DataFrame(rows).sort_values("regime").reset_index(drop=True)


# ---------- 打印 ----------

def print_ic_table(ic_df: pd.DataFrame):
    """格式化打印 IC 表格。"""
    print(f"\n{'='*80}")
    print(f"IC Analysis Results ({len(ic_df)} pairs)")
    print(f"{'='*80}")
    print(f"{'feature':<20} {'horizon':>8} {'ic':>10} {'rank_ic':>10} {'p_value':>10} {'n':>8}")
    print(f"{'-'*66}")

    for _, row in ic_df.iterrows():
        ic_str = f"{row['ic']:.4f}" if not np.isnan(row['ic']) else "nan"
        ric_str = f"{row['rank_ic']:.4f}" if not np.isnan(row['rank_ic']) else "nan"
        p_str = f"{row['p_value']:.4f}" if not np.isnan(row['p_value']) else "nan"

        # 标记显著性
        sig = ""
        if not np.isnan(row.get("p_value", np.nan)):
            if row["p_value"] < 0.01:
                sig = " **"
            elif row["p_value"] < 0.05:
                sig = " *"

        print(f"{row['feature']:<20} {row.get('horizon', 0):>8} {ic_str:>10} {ric_str:>10} {p_str:>10} {row['sample_count']:>8}{sig}")

    print(f"\n  ** p < 0.01   * p < 0.05")


# ---------- CLI ----------

def main():
    parser = argparse.ArgumentParser(description="Alpha IC Analysis - 信息系数分析")
    parser.add_argument("--symbol", type=str, default="BTCUSDT")
    parser.add_argument("--exchange", type=str, default="binance")
    parser.add_argument("--timeframe", type=str, default="1m")
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--source", type=str, default="parquet", choices=["parquet"])
    parser.add_argument("--output", type=str, default=None, help="输出 CSV 路径")
    parser.add_argument("--workers", type=int, default=None, help="线程数")

    args = parser.parse_args()

    print(f"Alpha IC Analysis: {args.symbol} | {args.exchange} | {args.days}d")
    print("=" * 50)

    # 1. 构建 feature matrix
    print("Loading feature matrix...")
    from research.alpha.feature_matrix import build_feature_matrix
    fm = build_feature_matrix(
        symbol=args.symbol,
        exchange=args.exchange,
        days=args.days,
        timeframe=args.timeframe,
    )
    print(f"  Features: {len(fm)} bars, {len(fm.columns)} columns")

    # 2. 计算 labels
    print("Computing labels...")
    from research.alpha.labels import compute_labels_from_df
    labels = compute_labels_from_df(fm)
    print(f"  Labels: {len(labels.columns)} columns")

    # 3. IC 分析
    print("Computing IC table (multi-threaded)...")
    ic_df = compute_ic_table(fm, labels, max_workers=args.workers)
    print_ic_table(ic_df)

    # 4. Regime 条件 IC
    print("\nClassifying regimes...")
    from research.alpha.regime_analysis import classify_regime, regime_summary
    fm = classify_regime(fm)
    print(regime_summary(fm).to_string(index=False))

    print("\nConditional IC by trend_regime:")
    for feat in ["funding_zscore", "volume_zscore", "trend_20"]:
        if feat not in fm.columns:
            continue
        cond = compute_conditional_ic(
            fm, labels, feat, "future_ret_5",
            regime_col="trend_regime", max_workers=args.workers,
        )
        print(f"\n  {feat} → future_ret_5:")
        for _, row in cond.iterrows():
            ic_str = f"{row['ic']:.4f}" if not np.isnan(row['ic']) else "nan"
            p_str = f"{row['p_value']:.4f}" if not np.isnan(row['p_value']) else "nan"
            print(f"    {row['regime']:<12} ic={ic_str}  p={p_str}  n={row['sample_count']}")

    # 5. 输出 CSV
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        ic_df.to_csv(output_path, index=False)
        print(f"\nSaved to {output_path}")

    # 总结
    sig_features = ic_df[ic_df["p_value"] < 0.05] if "p_value" in ic_df.columns else pd.DataFrame()
    print(f"\n{'='*80}")
    if len(sig_features) > 0:
        print(f"Found {len(sig_features)} significant feature-label pairs (p < 0.05):")
        for _, row in sig_features.iterrows():
            print(f"  {row['feature']} → {row['label']}: IC={row['ic']:.4f}, p={row['p_value']:.4f}")
    else:
        print("No significant feature-label pairs found (p < 0.05)")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
