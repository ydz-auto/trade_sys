"""
检查特征矩阵中的 MA 相关列
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

from research.alpha.feature_matrix import build_feature_matrix


fm = build_feature_matrix(
    symbol="BTCUSDT",
    exchange="binance",
    days=365,
    timeframe="1h",
    exclude_sources=["oi", "liquidation"]
)

print("特征矩阵列名 (包含 'ma' 或 'trend'):")
for col in sorted(fm.columns):
    if 'ma' in col.lower() or 'trend' in col.lower():
        print(f"  {col}")

print(f"\n所有列数量: {len(fm.columns)}")
