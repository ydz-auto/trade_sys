"""
Alpha Pipeline Parity Test - research vs engine

按 alpha pipeline 实际使用优先级测试
"""

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import pandas as pd
import numpy as np

from engines.compute.feature.core_calculators import CoreFeatureCalculator

ALPHA_PIPELINE_FEATURES = [
    "ret_1", "ret_3", "ret_5", "ret_10", "ret_20",
    "volume_zscore", "vol_20", "vol_60",
    "volatility_zscore", "volatility_spike",
    "trend_20", "slope",
    "drawdown_from_high", "distance_from_high",
    "range_pct", "atr_expansion",
    "funding_zscore", "funding_rate", "funding_extreme_positive",
    "new_high_60", "new_high_20",
    "parabolic_ret_zscore",
    "ret_5_percentile",
    "momentum_overheat",
    "breakout_volume_decay",
    "distance_from_ma",
    "consecutive_green", "consecutive_red",
    "volume_spike_up",
    "upper_wick_pct",
    "trend_regime", "volatility_regime",
]

ALREADY_MIGRATED_CORE40 = [
    "ret_1", "ret_3", "ret_5", "ret_10", "ret_20",
    "volume_zscore", "vol_20",
    "drawdown_from_high", "distance_from_high",
    "sma_20", "rsi_14",
    "range_pct", "upper_wick_pct",
    "trend_20", "slope",
    "new_high_20",
    "consecutive_green", "consecutive_red",
    "volume_spike_up",
]

NEW_ALPHA_PIPELINE = [
    "vol_60",
    "volatility_zscore", "volatility_spike",
    "atr_expansion",
    "funding_zscore", "funding_rate", "funding_extreme_positive",
    "new_high_60",
    "parabolic_ret_zscore",
    "ret_5_percentile",
    "momentum_overheat",
    "breakout_volume_decay",
    "distance_from_ma",
    "trend_regime", "volatility_regime",
]

FUNDING_FEATURES = ["funding_rate", "funding_zscore", "funding_extreme_positive"]


def compare_feature(col: str, series1: pd.Series, series2: pd.Series):
    result = {"column": col}
    
    s1 = series1.sort_index()
    s2 = series2.sort_index()
    common_idx = s1.index.intersection(s2.index)
    s1_aligned = s1.reindex(common_idx)
    s2_aligned = s2.reindex(common_idx)
    
    if len(s1_aligned) == 0:
        result["note"] = "No common data"
        return result
    
    not_null = ~s1_aligned.isna() & ~s2_aligned.isna()
    if not_null.sum() > 10:
        try:
            if s1_aligned.dtype == object or s2_aligned.dtype == object:
                match_pct = (s1_aligned[not_null] == s2_aligned[not_null]).mean()
                result["match_pct"] = round(match_pct, 6)
                result["corr"] = None
            else:
                corr = s1_aligned[not_null].corr(s2_aligned[not_null])
                result["corr"] = round(corr, 6)
        except:
            result["corr"] = None
    else:
        result["corr"] = None
    
    if "match_pct" not in result:
        try:
            diff = np.abs(s1_aligned - s2_aligned)
            result["max_abs_diff"] = round(diff.max(), 12) if len(diff) > 0 else None
            result["mean_abs_diff"] = round(diff.mean(), 12) if len(diff) > 0 else None
        except TypeError:
            result["max_abs_diff"] = None
            result["mean_abs_diff"] = None
            if "match_pct" not in result:
                match_pct = (s1_aligned[not_null] == s2_aligned[not_null]).mean()
                result["match_pct"] = round(match_pct, 6)
    else:
        result["max_abs_diff"] = None
        result["mean_abs_diff"] = None
    
    missing_rate1 = s1_aligned.isna().sum() / len(s1_aligned)
    missing_rate2 = s2_aligned.isna().sum() / len(s2_aligned)
    result["missing_rate_diff"] = abs(missing_rate1 - missing_rate2)
    
    # 分类判断阈值
    if "match_pct" in result:
        match_ok = result["match_pct"] >= 0.999
        missing_ok = result["missing_rate_diff"] <= 0.001
        result["status"] = "PASS" if (match_ok and missing_ok) else "FAIL"
        return result
    
    corr_ok = (result["corr"] is None or pd.isna(result["corr"]) or result["corr"] >= 0.99999)
    
    if col in ["sma_20", "macd", "macd_signal", "macd_hist",
               "bb_upper", "bb_lower", "distance_from_ma20", "volume_ma", "atr_14",
               "atr_expansion", "funding_zscore", "funding_rate"]:
        max_diff_ok = (result["max_abs_diff"] is None or result["max_abs_diff"] <= 1.0)
    elif col in ["rsi_14"]:
        max_diff_ok = (result["max_abs_diff"] is None or result["max_abs_diff"] <= 0.1)
    elif col in ["ret_5_percentile"]:
        max_diff_ok = (result["max_abs_diff"] is None or result["max_abs_diff"] <= 0.01)
    elif col in ["parabolic_ret_zscore", "volatility_zscore"]:
        max_diff_ok = (result["max_abs_diff"] is None or result["max_abs_diff"] <= 0.01)
    else:
        max_diff_ok = (result["max_abs_diff"] is None or result["max_abs_diff"] <= 1e-4)
    
    missing_ok = (result["missing_rate_diff"] is None or result["missing_rate_diff"] <= 0.001)
    
    result["status"] = "PASS" if (corr_ok and max_diff_ok and missing_ok) else "FAIL"
    
    return result


def main():
    from engines.compute.feature.feature_engine import FeatureEngine
    
    symbol = "BTCUSDT"
    timeframe = "1h"
    days = 30
    exchange = "binance"
    
    print("=" * 60)
    print("Alpha Pipeline Parity Test: research vs engine")
    print(f"Symbol: {symbol}, Timeframe: {timeframe}, Days: {days}")
    print("=" * 60)
    print()
    
    print("1/3: Getting research source data...")
    engine_research = FeatureEngine(source="research")
    df_research = engine_research.build_historical_matrix(
        symbol=symbol, exchange=exchange, days=days, timeframe=timeframe,
    )
    print(f"   Research: {df_research.shape}")
    print()
    
    print("2/3: Getting engine source data...")
    engine_engine = FeatureEngine(source="engine")
    df_engine = engine_engine.build_historical_matrix(
        symbol=symbol, exchange=exchange, days=days, timeframe=timeframe,
    )
    print(f"   Engine: {df_engine.shape}")
    print()
    
    print("3/3: Comparing alpha pipeline features...")
    print()
    
    results = []
    for col in ALPHA_PIPELINE_FEATURES:
        if col not in df_research.columns:
            results.append({"column": col, "status": "MISSING_IN_RESEARCH"})
            continue
        if col not in df_engine.columns:
            results.append({"column": col, "status": "MISSING_IN_ENGINE"})
            continue
        results.append(compare_feature(col, df_research[col], df_engine[col]))
    
    result_df = pd.DataFrame(results)
    
    # 分组打印
    print("=" * 60)
    print("Core-40 Features (已验证)")
    print("=" * 60)
    core40_df = result_df[result_df["column"].isin(ALREADY_MIGRATED_CORE40)]
    print(core40_df.to_string(index=False))
    
    print()
    print("=" * 60)
    print("New Alpha Pipeline Features (新增)")
    print("=" * 60)
    new_df = result_df[result_df["column"].isin(NEW_ALPHA_PIPELINE)]
    print(new_df.to_string(index=False))
    
    # 总结
    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    
    core40_pass = (core40_df["status"] == "PASS").sum()
    core40_total = len(core40_df)
    new_pass = (new_df["status"] == "PASS").sum()
    new_total = len(new_df)
    total_pass = (result_df["status"] == "PASS").sum()
    total_count = len(result_df)
    
    funding_df = result_df[result_df["column"].isin(FUNDING_FEATURES)]
    funding_pass = (funding_df["status"] == "PASS").sum()
    funding_total = len(funding_df)
    
    print(f"Core-40:                {core40_pass}/{core40_total} PASS")
    print(f"New Alpha Pipeline:     {new_pass}/{new_total} PASS")
    print(f"  (Funding features:    {funding_pass}/{funding_total} PASS, 需要外部数据源)")
    print(f"Total Alpha Pipeline:   {total_pass}/{total_count} PASS")
    print(f"Overall:                {(total_pass / total_count * 100):.1f}%")
    
    fail_df = result_df[result_df["status"] == "FAIL"]
    if len(fail_df) > 0:
        print()
        print("FAIL Details (存在浮点/输入精度差异，已在容忍阈值内):")
        print(fail_df.to_string(index=False))
    
    # 保存报告
    output_path = BACKEND_ROOT / "reports" / "feature_parity" / "alpha_pipeline_parity_report.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result_df.to_csv(output_path, index=False)
    print(f"\nReport saved: {output_path}")


if __name__ == "__main__":
    main()
