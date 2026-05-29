"""
检查用户提到的 Short 特征的类型和值分布
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
from research.alpha.feature_matrix import build_feature_matrix


def main():
    print("="*80)
    print("检查 Short 特征的类型和分布")
    print("="*80)
    
    fm = build_feature_matrix(
        symbol="BTCUSDT",
        exchange="binance",
        days=365,
        timeframe="1h",
        exclude_sources=["oi", "liquidation"]
    )
    
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
    
    print(f"\n{'特征':<25} {'类型':<12} {'唯一值数':<10} {'非零数':<10} {'示例值'}")
    print(f"{'-'*80}")
    
    for feat in user_features:
        if feat in fm.columns:
            col = fm[feat]
            dtype = str(col.dtype)
            unique_count = len(col.unique())
            non_zero_count = (col != 0).sum() if col.dtype != bool else col.sum()
            
            # 取一些示例值
            sample_values = col.dropna().unique()[:5]
            sample_str = ", ".join([str(v)[:8] for v in sample_values])
            
            print(f"{feat:<25} {dtype:<12} {unique_count:<10} {non_zero_count:<10} {sample_str}")
        else:
            print(f"{feat:<25} 不存在")
    
    # 检查是否有其他相关特征
    print(f"\n{'='*80}")
    print("所有包含 'volume' 的特征:")
    vol_features = [col for col in fm.columns if 'volume' in col.lower()]
    for col in vol_features:
        print(f"  {col}")
    
    print(f"\n所有包含 'breakout' 的特征:")
    breakout_features = [col for col in fm.columns if 'breakout' in col.lower()]
    for col in breakout_features:
        print(f"  {col}")


if __name__ == "__main__":
    main()
