"""
测试修复后的 TorchFeatureCalculator
"""
import sys
import os
from pathlib import Path

backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

import pandas as pd
import numpy as np

print("=" * 80)
print("测试 TorchFeatureCalculator")
print("=" * 80)
print()

try:
    from engines.compute.feature.torch_calculator import TorchFeatureCalculator
    print("✓ TorchFeatureCalculator 导入成功")
except Exception as e:
    print(f"✗ TorchFeatureCalculator 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    calculator = TorchFeatureCalculator()
    print("✓ TorchFeatureCalculator 初始化成功")
except Exception as e:
    print(f"✗ TorchFeatureCalculator 初始化失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# 测试1: 单条特征计算
print("=" * 80)
print("测试1: 单条特征计算")
print("=" * 80)

try:
    features = calculator.compute(
        symbol="BTCUSDT",
        open_price=42000.0,
        high=42500.0,
        low=41800.0,
        close=42200.0,
        volume=1000.0
    )
    print("✓ 单条特征计算成功")
    print(f"  计算得到的特征: {list(features.keys())}")
except Exception as e:
    print(f"✗ 单条特征计算失败: {e}")
    import traceback
    traceback.print_exc()

print()

# 测试2: 批量特征计算
print("=" * 80)
print("测试2: 批量特征计算")
print("=" * 80)

n_rows = 100
dates = pd.date_range(start="2024-01-01", periods=n_rows, freq="H")
df = pd.DataFrame({
    "timestamp": dates,
    "open": 40000.0 + np.cumsum(np.random.randn(n_rows) * 100),
    "high": 40000.0 + np.cumsum(np.random.randn(n_rows) * 100) + 50,
    "low": 40000.0 + np.cumsum(np.random.randn(n_rows) * 100) - 50,
    "close": 40000.0 + np.cumsum(np.random.randn(n_rows) * 100),
    "volume": 1000.0 + np.random.randn(n_rows) * 100
})

try:
    # 先计算更多数据以便特征有足够的历史数据
    for _, row in df.head(50).iterrows():
        calculator.compute(
            symbol="BTCUSDT",
            open_price=float(row['open']),
            high=float(row['high']),
            low=float(row['low']),
            close=float(row['close']),
            volume=float(row['volume'])
        )
    
    # 现在测试批量计算
    result_df = calculator.compute_batch(df.tail(50), use_gpu=False)
    print("✓ 批量特征计算 (CPU) 成功")
    print(f"  计算得到的特征列数: {len(result_df.columns)}")
except Exception as e:
    print(f"✗ 批量特征计算失败: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 80)
print("测试完成")
print("=" * 80)
