"""
Short Features Validation - 做空 Alpha Features 独立验证脚本

使用方法：
    cd backend
    python -m research.alpha.features_short.validate_short_features --symbol BTCUSDT --days 365

验证流水线：
    Feature → IC → Conditional IC → Signal Test → WF → Stability

输出报告：
    reports/alpha/short_features_ic_{symbol}_{days}d.csv
    reports/alpha/short_features_signal_{symbol}_{days}d.csv
"""

import sys
from pathlib import Path
from typing import List, Optional, Dict
import argparse
from datetime import datetime

import numpy as np
import pandas as pd

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from research.alpha.feature_matrix import build_feature_matrix_from_df
from research.alpha.labels import compute_labels_from_df
from research.alpha.ic_analysis import compute_ic_table
from research.alpha.funding_regime_signal import run_signal_test
from research.stability.analyzer import StabilityAnalyzer
from .short_features_registry import (
    ALL_SHORT_FEATURES,
    SHORT_FEATURES_BY_FAMILY,
    get_short_features_by_family,
    print_short_feature_summary,
)


def validate_short_features_by_family(
    feature_matrix: pd.DataFrame,
    label_df: pd.DataFrame,
    family: str,
    output_dir: str = "reports/alpha/",
) -> pd.DataFrame:
    """验证单个 Short Feature Family"""
    features = get_short_features_by_family(family)
    available = [f for f in features if f in feature_matrix.columns]

    if not available:
        print(f"  No features available for {family}")
        return pd.DataFrame()

    print(f"\n  Family: {family} ({len(available)} features)")

    ic_results = compute_ic_table(
        feature_matrix=feature_matrix,
        label_df=label_df,
        features=available,
        labels=["future_ret_1", "future_ret_3", "future_ret_5", "future_ret_10"],
    )

    return ic_results


def run_short_feature_validation(
    symbol: str = "BTCUSDT",
    days: int = 365,
    timeframe: str = "1h",
    exchange: str = "binance",
    output_dir: str = "reports/alpha/",
    families: Optional[List[str]] = None,
) -> Dict[str, pd.DataFrame]:
    """
    运行 Short Features 验证流水线

    Args:
        symbol: 交易对
        days: 回看天数
        timeframe: K线周期
        exchange: 交易所
        output_dir: 输出目录
        families: 要验证的家族列表（None=全部）

    Returns:
        {family: ic_results} 字典
    """
    print("\n" + "=" * 70)
    print(f"Short Feature Validation - {symbol}")
    print("=" * 70)

    print(f"\n[1/4] Loading data...")
    from infrastructure.storage.data_lake.file_reader import FileDataLakeReader

    reader = FileDataLakeReader()
    klines = reader.load_klines(exchange, symbol, timeframe=timeframe)
    if klines is None or len(klines) == 0:
        raise ValueError(f"No data for {symbol} {timeframe}")

    klines["timestamp"] = pd.to_datetime(klines["timestamp"])
    cutoff = klines["timestamp"].max() - pd.Timedelta(days=days)
    klines = klines[klines["timestamp"] >= cutoff].copy()

    print(f"  Loaded {len(klines)} bars: {klines['timestamp'].min().date()} ~ {klines['timestamp'].max().date()}")

    print(f"\n[2/4] Building feature matrix...")
    feat_df = build_feature_matrix_from_df(
        klines,
        funding=None,
        oi=None,
        trades=None,
        timeframe=timeframe,
    )
    print(f"  Built {len(feat_df.columns)} features")

    print(f"\n[3/4] Computing labels...")
    label_df = compute_labels_from_df(feat_df)
    print(f"  Computed {len(label_df.columns)} labels")

    print(f"\n[4/4] Running IC analysis...")

    if families is None:
        families = list(SHORT_FEATURES_BY_FAMILY.keys())

    all_results = {}
    for family in families:
        if family not in SHORT_FEATURES_BY_FAMILY:
            continue
        results = validate_short_features_by_family(
            feature_matrix=feat_df,
            label_df=label_df,
            family=family,
            output_dir=output_dir,
        )
        if len(results) > 0:
            all_results[family] = results

    if not all_results:
        print("\nNo results generated!")
        return {}

    combined = pd.concat(all_results.values(), ignore_index=True)

    combined = combined.sort_values("rank_ic", ascending=False)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    ic_file = output_path / f"short_features_ic_{symbol}_{days}d.csv"
    combined.to_csv(ic_file, index=False)
    print(f"\nSaved IC results to: {ic_file}")

    print("\n" + "=" * 70)
    print("Top 10 Short Features by Rank IC:")
    print("=" * 70)
    top10 = combined.head(10)
    print(f"\n{'Feature':<30} {'Family':<20} {'Horizon':<8} {'IC':>8} {'Rank IC':>10} {'Count':>8}")
    print("-" * 90)
    for _, row in top10.iterrows():
        print(f"{row['feature']:<30} {row['alpha_family']:<20} {row['horizon']:<8} {row['ic']:>8.4f} {row['rank_ic']:>10.4f} {row['sample_count']:>8}")

    print("\n" + "=" * 70)
    print("Summary by Family:")
    print("=" * 70)
    summary = combined.groupby("alpha_family").agg({
        "rank_ic": ["mean", "max", "count"],
        "ic": ["mean", "max"],
    }).round(4)
    print(summary)

    return all_results


def main():
    parser = argparse.ArgumentParser(description="Short Feature Validation")
    parser.add_argument("--symbol", type=str, default="BTCUSDT")
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--timeframe", type=str, default="1h")
    parser.add_argument("--exchange", type=str, default="binance")
    parser.add_argument("--output", type=str, default="reports/alpha/")
    parser.add_argument("--family", type=str, default=None, help="Specific family to validate")
    parser.add_argument("--list", action="store_true", help="List all short features")

    args = parser.parse_args()

    if args.list:
        print_short_feature_summary()
        return

    families = [args.family] if args.family else None

    run_short_feature_validation(
        symbol=args.symbol,
        days=args.days,
        timeframe=args.timeframe,
        exchange=args.exchange,
        output_dir=args.output,
        families=families,
    )


if __name__ == "__main__":
    main()
