"""
检查用户提到的 Short 特征是否存在
"""
import warnings
warnings.filterwarnings("ignore")

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import os
os.environ["CUDA_VISIBLE_DEVICES"] = ""

from research.alpha.features.matrix import build_feature_matrix


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

print("检查用户提到的 Short 特征:")
for feat in user_features:
    found = feat in fm.columns
    if found:
        print(f"✓ {feat}")
    else:
        # 检查是否有类似的列
        similar = [col for col in fm.columns if feat.lower() in col.lower()]
        if similar:
            print(f"✗ {feat} - 但找到类似: {similar}")
        else:
            print(f"✗ {feat}")

print(f"\n所有列数量: {len(fm.columns)}")
