"""
完整 Alpha 分析流水线 - Full Analysis Pipeline
"""

import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

import pandas as pd
import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def run_full_analysis(
    symbol: str = "BTCUSDT",
    exchange: str = "binance",
    timeframe: str = "1h",
    days: int = 90,
    output_dir: str = "reports/alpha",
    skip_walk_forward: bool = False,
):
    """
    运行完整的 Alpha 分析流程：
    1. 特征可用性审计
    2. READY features 批量 IC
    3. READY features signal test
    4. Leaderboard
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("=" * 80)
    print("Alpha Full Analysis Pipeline")
    print("=" * 80)
    print(f"Symbol: {symbol}")
    print(f"Exchange: {exchange}")
    print(f"Timeframe: {timeframe}")
    print(f"Days: {days}")
    print(f"Output: {output_dir}")
    print()

    # ========== Step 1: Feature Availability Audit ==========
    print("\n" + "=" * 80)
    print("Step 1: Feature Availability Audit")
    print("=" * 80)

    from research.alpha.feature_availability_audit import (
        run_availability_audit,
        print_ready_features,
        FeatureStatus,
    )

    audit_df = run_availability_audit(
        symbol=symbol,
        exchange=exchange,
        timeframe=timeframe,
        days=days,
    )

    audit_output = output_path / f"feature_audit_{symbol}_{days}d_{timestamp}.csv"
    audit_df.to_csv(audit_output, index=False)
    print(f"\nSaved audit report: {audit_output}")

    ready_features = audit_df[audit_df["status"] == FeatureStatus.READY]["feature"].tolist()
    print(f"\nFound {len(ready_features)} READY features:")
    print_ready_features(audit_df)

    if len(ready_features) == 0:
        print("\n⚠️  No READY features found. Pipeline stopped.")
        return audit_df, None, None, None

    # ========== Step 2: Load data for analysis ==========
    print("\n" + "=" * 80)
    print("Step 2: Loading data for analysis")
    print("=" * 80)

    from research.alpha.feature_matrix import build_feature_matrix
    from research.alpha.labels import compute_labels_from_df
    from research.alpha.regime_analysis import classify_regime

    fm = build_feature_matrix(
        symbol=symbol,
        exchange=exchange,
        days=days,
        timeframe=timeframe,
    )
    print(f"  Feature matrix: {len(fm)} bars, {len(fm.columns)} columns")

    labels = compute_labels_from_df(fm)
    print(f"  Labels: {len(labels.columns)} columns")

    fm = classify_regime(fm)
    print("  Regimes classified")

    # ========== Step 3: READY features 批量 IC ==========
    print("\n" + "=" * 80)
    print("Step 3: READY features batch IC analysis")
    print("=" * 80)

    from research.alpha.ic_analysis import compute_ic_table, print_ic_table

    ic_df = compute_ic_table(
        fm,
        labels,
        features=ready_features,
        max_workers=4,
    )

    if len(ic_df) > 0:
        print_ic_table(ic_df)

        ic_output = output_path / f"ic_analysis_{symbol}_{days}d_{timestamp}.csv"
        ic_df.to_csv(ic_output, index=False)
        print(f"\nSaved IC analysis: {ic_output}")

        # Find significant ICs
        sig_ic = ic_df[ic_df["p_value"] < 0.05] if "p_value" in ic_df.columns else pd.DataFrame()
        if len(sig_ic) > 0:
            print(f"\n✅ Found {len(sig_ic)} significant (p<0.05) ICs")
    else:
        print("  No IC results computed")
        ic_df = pd.DataFrame()

    # ========== Step 4: READY features signal test ==========
    print("\n" + "=" * 80)
    print("Step 4: READY features signal test")
    print("=" * 80)

    # First, we need to create alpha definitions for all READY features
    # Let's use existing pipeline infrastructure
    from research.alpha.pipeline import AlphaPipeline

    # For each READY feature, create a simple reversal definition
    from research.alpha.strategy_alpha_registry import AlphaDefinition, AlphaRegistry

    # First, save existing registry
    existing_registry = AlphaRegistry._registry.copy()

    try:
        # Create simple alpha definitions for READY features
        for feat in ready_features:
            feat_lower = feat.lower()
            direction = "both"
            if any(k in feat_lower for k in ["ret_", "drawdown", "trend_"]):
                direction = "long"  # reversal

            alpha_name = f"auto_{feat}"

            # Check if already exists
            if alpha_name not in existing_registry:
                AlphaRegistry.register(AlphaDefinition(
                    name=alpha_name,
                    features=[feat],
                    mode="reversal",
                    direction=direction,
                    primary_feature=feat,
                    signal_direction_map={feat: "negative_means_long" if direction == "long" else "positive_means_short"},
                ))

        # Now run pipeline for all these
        print(f"\nRunning pipeline for {len(ready_features)} READY features...")

        pipeline = AlphaPipeline(
            symbols=[symbol],
            timeframes=[timeframe],
            days=days,
            skip_walk_forward=skip_walk_forward,
            output_dir=output_dir,
            exchange=exchange,
        )

        # Get all auto_* strategies
        auto_strategies = [
            d.name for d in AlphaRegistry.list_all()
            if d.name.startswith("auto_")
        ]

        if auto_strategies:
            pipeline_result = pipeline.run(auto_strategies)

            # Also run with the original active strategies
            print("\n" + "=" * 80)
            print("Step 5: Original active strategies pipeline")
            print("=" * 80)

            active_strategies = [d.name for d in AlphaRegistry.get_active() if not d.name.startswith("auto_")]
            if active_strategies:
                pipeline.run(active_strategies)

            print("\n" + "=" * 80)
            print("Pipeline Complete!")
            print("=" * 80)

            return audit_df, ic_df, pipeline_result, fm
        else:
            print("No auto strategies created")
            return audit_df, ic_df, None, fm

    finally:
        # Restore original registry
        AlphaRegistry._registry = existing_registry


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Full Alpha Analysis Pipeline")
    parser.add_argument("--symbol", type=str, default="BTCUSDT")
    parser.add_argument("--exchange", type=str, default="binance")
    parser.add_argument("--timeframe", type=str, default="1h")
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--output-dir", type=str, default="reports/alpha")
    parser.add_argument("--skip-walk-forward", action="store_true", default=True,
                        help="Skip walk-forward validation (faster)")

    args = parser.parse_args()

    run_full_analysis(
        symbol=args.symbol,
        exchange=args.exchange,
        timeframe=args.timeframe,
        days=args.days,
        output_dir=args.output_dir,
        skip_walk_forward=args.skip_walk_forward,
    )


if __name__ == "__main__":
    main()
