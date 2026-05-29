"""
找到 BTCUSDT 上 IC Top5 的 short 特征（负 IC）
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

import numpy as np
import pandas as pd
from research.alpha.feature_matrix import build_feature_matrix
from research.alpha.labels import compute_labels_from_df
from research.alpha.ic_analysis import compute_ic_table


def main():
    print("="*80)
    print("寻找 BTCUSDT 上 IC Top5 的 Short 特征")
    print("="*80)
    
    fm = build_feature_matrix(
        symbol="BTCUSDT",
        exchange="binance",
        days=365,
        timeframe="1h",
        exclude_sources=["oi", "liquidation"]
    )
    
    labels = compute_labels_from_df(fm)
    
    print(f"特征矩阵形状: {fm.shape}")
    print(f"标签形状: {labels.shape}")
    
    # 计算 IC
    ic_df = compute_ic_table(fm, labels)
    
    # 找到负 IC 的特征（Short 策略有效）
    short_candidates = ic_df[ic_df["rank_ic"] < 0].copy()
    short_candidates["abs_ic"] = short_candidates["rank_ic"].abs()
    
    print(f"\n负 IC 特征数量: {len(short_candidates)}")
    
    # 按绝对值排序
    short_candidates = short_candidates.sort_values("abs_ic", ascending=False)
    
    print(f"\nShort IC Top 20:")
    print(f"{'特征':<30} {'Horizon':<10} {'Rank IC':<12} {'Rank P':<10}")
    print(f"{'-'*60}")
    
    for _, row in short_candidates.head(20).iterrows():
        print(f"{row['feature']:<30} {row['horizon']:<10} {row['rank_ic']:<12.4f} {row['rank_p_value']:<10.4f}")
    
    # 获取唯一特征名（去重）
    unique_features = short_candidates.drop_duplicates("feature").sort_values("abs_ic", ascending=False)
    print(f"\n去重后的 Short IC Top10:")
    for _, row in unique_features.head(10).iterrows():
        print(f"{row['feature']:<30} | rank_ic={row['rank_ic']:.4f}")
    
    return unique_features["feature"].head(10).tolist()


if __name__ == "__main__":
    top_features = main()
    print(f"\nShort IC Top10 特征列表:")
    print(top_features)
