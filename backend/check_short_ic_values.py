"""
检查用户提到的 Short 特征的 IC 值和方向
"""
import warnings
warnings.filterwarnings("ignore")

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import os
os.environ["CUDA_VISIBLE_DEVICES"] = ""

import pandas as pd
from research.alpha.feature_matrix import build_feature_matrix
from research.alpha.labels import compute_labels_from_df
from research.alpha.ic_analysis import compute_ic_table


def main():
    print("="*80)
    print("检查用户提到的 Short 特征的 IC 值")
    print("="*80)
    
    fm = build_feature_matrix(
        symbol="BTCUSDT",
        exchange="binance",
        days=365,
        timeframe="1h",
        exclude_sources=["oi", "liquidation"]
    )
    
    labels = compute_labels_from_df(fm)
    ic_df = compute_ic_table(fm, labels)
    
    user_features = [
        "volume_climax",
        "breakout_failure",
        "funding_oi_combined",
        "double_top_probability",
        "momentum_divergence",
        "new_high_60",
        "breakout_volume_decay",
        "volume_spike_up",
        "volume_zscore",
    ]
    
    print(f"\n{'特征':<25} {'Horizon':<8} {'Rank IC':<12} {'Rank P':<10} {'方向'}")
    print(f"{'-'*65}")
    
    for feat in user_features:
        feat_rows = ic_df[ic_df["feature"] == feat]
        if len(feat_rows) > 0:
            best_row = feat_rows.loc[feat_rows["rank_ic"].abs().idxmax()]
            direction = "SHORT ✓" if best_row["rank_ic"] < 0 else "LONG"
            print(f"{feat:<25} {best_row['horizon']:<8} {best_row['rank_ic']:<12.4f} {best_row['rank_p_value']:<10.4f} {direction}")
        else:
            print(f"{feat:<25} -         -             -            不存在")
    
    # 汇总
    print(f"\n{'='*65}")
    short_candidates = []
    for feat in user_features:
        feat_rows = ic_df[ic_df["feature"] == feat]
        if len(feat_rows) > 0:
            best_row = feat_rows.loc[feat_rows["rank_ic"].abs().idxmax()]
            if best_row["rank_ic"] < 0 and abs(best_row["rank_ic"]) > 0.01:
                short_candidates.append((feat, best_row["rank_ic"]))
    
    short_candidates.sort(key=lambda x: abs(x[1]), reverse=True)
    print(f"适合 Short 的特征（负 IC，绝对值 > 0.01）:")
    for feat, ic in short_candidates:
        print(f"  {feat:<25} | rank_ic={ic:.4f}")


if __name__ == "__main__":
    main()
