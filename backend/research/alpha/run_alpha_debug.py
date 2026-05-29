"""
Alpha Pipeline Debug Runner - 分步调试版本

用于定位崩溃问题，支持：
1. 按阶段独立运行
2. 单线程模式
3. 最小化调试开关
"""

import sys
import os
from pathlib import Path
from typing import List, Optional, Dict
import argparse
from datetime import datetime

os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

import numpy as np
import pandas as pd

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def print_stage_header(stage: str):
    print(f"\n{'='*70}")
    print(f"  STAGE: {stage.upper()}")
    print(f"{'='*70}")


def stage_feature_build(args):
    """Stage 1: Build Feature Matrix"""
    print_stage_header("feature_build")
    
    try:
        from research.alpha.feature_matrix import build_feature_matrix
        
        print(f"  Loading data: {args.symbol} {args.timeframe} {args.days}d")
        feat_df = build_feature_matrix(
            symbol=args.symbol,
            days=args.days,
            timeframe=args.timeframe,
        )
        
        print(f"  Feature matrix shape: {feat_df.shape}")
        print(f"  Columns: {len(feat_df.columns)} total")
        
        output_file = Path(args.output) / f"feature_matrix_{args.symbol}_{args.timeframe}_{args.days}d.csv"
        feat_df.to_csv(output_file, index=False)
        print(f"  Saved to: {output_file}")
        
        return True, feat_df
    
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def stage_ic(args, feat_df):
    """Stage 2: IC Analysis"""
    print_stage_header("ic_analysis")
    
    try:
        from research.alpha.labels import compute_labels_from_df
        from research.alpha.ic_analysis import compute_ic_table
        
        print(f"  Computing labels...")
        label_df = compute_labels_from_df(feat_df)
        print(f"  Labels: {list(label_df.columns)}")
        
        features_to_check = [
            "distance_from_ma20", "distance_from_ma60", "distance_from_vwap",
            "zscore_price", "ma20_slope_zscore", "price_deviation_band",
            "ret_3_acceleration", "ret_5_acceleration", "ret_10_acceleration",
            "slope_acceleration", "curvature", "velocity_increase", "momentum_divergence",
            "distance_from_high", "upper_shadow_ratio", "consecutive_green",
            "close_position_in_range", "volume_climax",
            "breakout_strength", "breakout_failure", "breakout_retraction",
            "double_top_probability",
            "funding_zscore_long", "oi_zscore_long", "basis_zscore",
            "long_short_ratio", "funding_oi_combined", "crowded_long_score",
            "ret_1", "ret_3", "ret_5", "ret_10",
            "funding_zscore", "volume_zscore", "range_pct",
        ]
        
        available = [f for f in features_to_check if f in feat_df.columns]
        print(f"  Checking {len(available)} features")
        
        if not available:
            return False, None
        
        print(f"  Running IC analysis...")
        ic_results = compute_ic_table(
            feature_matrix=feat_df,
            label_df=label_df,
            features=available,
            labels=["future_ret_1", "future_ret_3", "future_ret_5", "future_ret_10"],
        )
        
        ic_results = ic_results.sort_values("rank_ic", ascending=False)
        
        output_file = Path(args.output) / f"ic_results_{args.symbol}_{args.timeframe}_{args.days}d.csv"
        ic_results.to_csv(output_file, index=False)
        print(f"  Saved IC results to: {output_file}")
        
        print(f"\n  TOP 10 FEATURES BY RANK IC:")
        print(f"  {'Feature':<25} {'Horizon':<10} {'IC':>10} {'Rank IC':>10}")
        print(f"  {'-'*70}")
        for _, row in ic_results.head(10).iterrows():
            print(f"  {row['feature']:<25} {row['horizon']:<10} {row['ic']:>10.4f} {row['rank_ic']:>10.4f}")
        
        strong_ic = ic_results[ic_results["rank_ic"].abs() > 0.02]
        print(f"\n  Features with |Rank IC| > 0.02: {len(strong_ic)}")
        
        return True, ic_results
    
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def stage_signal_test(args, feat_df):
    """Stage 3: Signal Test"""
    print_stage_header("signal_test")
    
    try:
        from research.alpha.funding_regime_signal import run_signal_test
        
        close = feat_df["close"].values
        regime_series = feat_df.get("regime")
        if regime_series is None:
            regime_labels = np.zeros(len(feat_df))
        else:
            regime_labels = regime_series.values
        
        short_features = [
            "funding_zscore_long",
            "crowded_long_score",
            "distance_from_ma20",
            "ret_5_acceleration",
            "volume_climax",
            "upper_shadow_ratio",
            "breakout_failure",
            "oi_zscore_long",
        ]
        
        available_features = [f for f in short_features if f in feat_df.columns]
        print(f"  Testing {len(available_features)} short features")
        
        results = []
        
        for feature_name in available_features:
            feature_vals = feat_df[feature_name].values
            
            for threshold_pct in [90, 95]:
                valid_vals = feature_vals[~np.isnan(feature_vals)]
                if len(valid_vals) == 0:
                    continue
                threshold = np.percentile(valid_vals, threshold_pct)
                
                for holding_bars in [5, 10]:
                    result = run_signal_test(
                        close=close,
                        feature_vals=feature_vals,
                        regime_labels=regime_labels,
                        feature_threshold=threshold,
                        holding_bars=holding_bars,
                        direction="short",
                        target_regimes=None,
                        taker_fee=0.001,
                    )
                    
                    if result and result.get("trades", 0) > 5:
                        results.append({
                            "feature": feature_name,
                            "threshold_pct": threshold_pct,
                            "holding_bars": holding_bars,
                            "profit_factor": result.get("profit_factor", 0),
                            "win_rate": result.get("win_rate", 0),
                            "sharpe": result.get("sharpe", 0),
                            "trades": result.get("trades", 0),
                        })
        
        if results:
            results_df = pd.DataFrame(results).sort_values("profit_factor", ascending=False)
            
            output_file = Path(args.output) / f"signal_test_{args.symbol}_{args.timeframe}_{args.days}d.csv"
            results_df.to_csv(output_file, index=False)
            print(f"  Saved signal test results to: {output_file}")
            
            print(f"\n  SIGNAL TEST RESULTS (TOP 15):")
            print(f"  {'Feature':<20} {'Thresh':<8} {'Hold':<6} {'PF':>8} {'WR%':>8} {'Sharpe':>8} {'Trades':>8}")
            print(f"  {'-'*75}")
            for _, row in results_df.head(15).iterrows():
                pf = row["profit_factor"]
                wr = row["win_rate"] * 100
                status = "✓" if pf > 1.0 else "✗"
                print(f"  {status} {row['feature']:<19} {row['threshold_pct']:<8} {row['holding_bars']:<6} {pf:>8.2f} {wr:>7.1f}% {row['sharpe']:>8.2f} {int(row['trades']):>8}")
        
        return True, results
    
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def main():
    parser = argparse.ArgumentParser(description="Alpha Pipeline Debug Runner")
    
    parser.add_argument("--stage", type=str, action="append", required=True,
                        choices=["feature_build", "ic", "signal_test", "all"],
                        help="Stage(s) to run")
    
    parser.add_argument("--symbol", type=str, default="BTCUSDT")
    parser.add_argument("--timeframe", type=str, default="1h")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--output", type=str, default="reports/alpha/debug/")
    
    args = parser.parse_args()
    
    os.makedirs(args.output, exist_ok=True)
    
    if "all" in args.stage:
        args.stage = ["feature_build", "ic", "signal_test"]
    
    print(f"\n{'='*70}")
    print(f"  ALPHA PIPELINE DEBUG RUNNER")
    print(f"  Timestamp: {datetime.now()}")
    print(f"  Symbol: {args.symbol}")
    print(f"  Timeframe: {args.timeframe}")
    print(f"  Days: {args.days}")
    print(f"  Workers: {args.workers}")
    print(f"  Stages: {', '.join(args.stage)}")
    print(f"{'='*70}")
    
    feat_df = None
    stage_results = {}
    
    stages_order = ["feature_build", "ic", "signal_test"]
    stages_to_run = [s for s in stages_order if s in args.stage]
    
    for stage in stages_to_run:
        if stage == "feature_build":
            success, data = stage_feature_build(args)
            if success:
                feat_df = data
            stage_results[stage] = success
        
        elif stage == "ic" and feat_df is not None:
            success, data = stage_ic(args, feat_df)
            stage_results[stage] = success
        
        elif stage == "signal_test" and feat_df is not None:
            success, data = stage_signal_test(args, feat_df)
            stage_results[stage] = success
        
        if not stage_results.get(stage, False):
            print(f"\n  {'='*70}")
            print(f"  ABORTING: Stage {stage} failed")
            print(f"  {'='*70}")
            break
    
    print(f"\n{'='*70}")
    print(f"  PIPELINE SUMMARY")
    print(f"{'='*70}")
    print(f"\n  {'Stage':<20} {'Status':<10}")
    print(f"  {'-'*30}")
    for stage in stages_to_run:
        status = "SUCCESS" if stage_results.get(stage, False) else "FAILED"
        print(f"  {stage:<20} {status:<10}")
    
    success_count = sum(stage_results.values())
    total_count = len(stage_results)
    print(f"\n  Overall: {success_count}/{total_count} stages completed successfully")


if __name__ == "__main__":
    main()
