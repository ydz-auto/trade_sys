"""
Scan alpha pipeline for actually used features and generate used_feature_list.csv
"""

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import pandas as pd


def scan_registry_features():
    from research.alpha.registry.alpha_registry import AlphaRegistry
    
    features = set()
    for defn in AlphaRegistry.list_all():
        for f in defn.features:
            features.add(f)
    
    return features


def scan_signal_strategy_features():
    return {
        "trend_20", "vol_20", "vol_60",
        "funding_zscore", "funding_rate", "volume_zscore",
        "trend_regime", "vol_regime",
    }


def scan_ic_default_features():
    return {
        "funding_rate", "funding_zscore", "volume_zscore",
        "vol_20", "vol_60", "trend_20", "ret_1", "ret_5", "ret_10",
    }


def scan_pipeline_features():
    return {
        "distance_from_ma", "momentum_overheat",
        "breakout_volume_decay", "ret_5_percentile",
    }


def main():
    registry_features = scan_registry_features()
    signal_features = scan_signal_strategy_features()
    ic_features = scan_ic_default_features()
    pipeline_features = scan_pipeline_features()
    
    all_used = registry_features | signal_features | ic_features | pipeline_features
    
    # 分类
    already_migrated = {
        "ret_1", "ret_3", "ret_5", "ret_10", "ret_20",
        "volume_zscore", "vol_20", "drawdown_from_high", "distance_from_high",
        "sma_20", "rsi_14",
        "range_pct", "body_pct", "upper_wick_pct", "lower_wick_pct",
        "volume_ma", "volume_ratio",
        "macd", "macd_signal", "macd_hist",
        "bb_upper", "bb_lower", "bb_width",
        "atr_14",
        "trend_20", "slope",
        "new_high_20",
        "distance_from_ma20",
        "consecutive_green", "consecutive_red",
        "volume_spike_up",
    }
    
    engine_only_already = {
        "log_ret_1", "log_ret_5", "volume_zscore_50",
        "ema_12", "ema_26", "new_low_20",
        "vol_10", "vol_50", "price_volume_corr",
    }
    
    rows = []
    for feat in sorted(all_used):
        source = []
        if feat in registry_features:
            source.append("registry")
        if feat in signal_features:
            source.append("signal")
        if feat in ic_features:
            source.append("ic")
        if feat in pipeline_features:
            source.append("pipeline")
        
        if feat in already_migrated:
            status = "MIGRATED_CORE40"
        elif feat in engine_only_already:
            status = "ENGINE_ONLY"
        else:
            status = "TODO"
        
        rows.append({
            "feature": feat,
            "status": status,
            "used_by": "|".join(source),
        })
    
    df = pd.DataFrame(rows)
    
    # 打印统计
    print("=" * 60)
    print("Alpha Pipeline Used Feature List")
    print("=" * 60)
    print(f"Total features used by alpha pipeline: {len(df)}")
    print()
    
    for status in ["MIGRATED_CORE40", "ENGINE_ONLY", "TODO"]:
        subset = df[df["status"] == status]
        print(f"{status}: {len(subset)}")
        for _, row in subset.iterrows():
            print(f"  {row['feature']} ({row['used_by']})")
        print()
    
    # 保存
    output_path = BACKEND_ROOT / "reports" / "feature_parity" / "used_feature_list.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"Saved: {output_path}")
    
    # 输出 TODO 列表
    todo_features = df[df["status"] == "TODO"]["feature"].tolist()
    print(f"\nNext batch to migrate ({len(todo_features)} features):")
    print(todo_features)


if __name__ == "__main__":
    main()
