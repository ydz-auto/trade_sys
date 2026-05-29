"""最小化测试：验证空头策略基本运行"""
import sys
from pathlib import Path
BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from research.alpha.feature_matrix import build_feature_matrix
from research.alpha.strategy_alpha_registry import AlphaRegistry

print("=" * 60)
print("Step 1: 检查策略注册表")
print("=" * 60)

short_strategies = [s for s in AlphaRegistry.get_active() if s.direction == "short"]
print(f"找到 {len(short_strategies)} 个空头策略:")
for s in short_strategies:
    print(f"  - {s.name}: features={s.features}, direction={s.direction}")

print("\n" + "=" * 60)
print("Step 2: 加载特征矩阵 (BTCUSDT, 1h, 7天, 无OI/trades)")
print("=" * 60)

try:
    df = build_feature_matrix(
        symbol="BTCUSDT",
        exchange="binance",
        days=7,
        timeframe="1h",
        exclude_sources=["oi", "trades"]
    )
    print(f"✓ 特征矩阵加载成功!")
    print(f"  Shape: {df.shape}")
    print(f"  Columns: {len(df.columns)} 列")
    
    # 检查 SHORT_EXHAUSTION 特征是否存在
    required_features = [
        "distance_from_high",
        "parabolic_ret_zscore",
        "volatility_spike",
        "upper_wick_pct",
        "consecutive_green",
        "new_high_60",
        "funding_zscore",
        "ret_5_percentile",
        "volume_spike_up",
        "momentum_overheat",
        "breakout_volume_decay",
        "distance_from_ma"
    ]
    missing = [f for f in required_features if f not in df.columns]
    if missing:
        print(f"⚠️  缺失特征: {missing}")
    else:
        print("✓ 所有 SHORT_EXHAUSTION 特征都存在")
    
    # 检查样本数据
    sample = df.tail(3)
    print("\n样本数据 (最后3行):")
    cols_to_show = ["timestamp", "close", "funding_zscore", "distance_from_high", "rsi_14"]
    cols_to_show = [c for c in cols_to_show if c in df.columns]
    print(sample[cols_to_show])
    
except Exception as e:
    print(f"✗ 特征矩阵加载失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("Step 3: 运行 pipeline 的小版本")
print("=" * 60)
print("尝试运行最小 pipeline 命令...")

import subprocess
import sys
cmd = [
    sys.executable,
    "-m", "research.alpha.pipeline",
    "--strategy", "funding_trap_short",
    "--symbols", "BTCUSDT",
    "--timeframes", "1h",
    "--days", "7",
    "--exclude-sources", "oi,trades",
    "--skip-walk-forward",
    "--skip-stability"
]
print(f"命令: {' '.join(cmd)}")

try:
    result = subprocess.run(cmd, cwd=str(BACKEND_ROOT), capture_output=True, text=True)
    print("\nstdout:")
    print(result.stdout)
    if result.stderr:
        print("\nstderr:")
        print(result.stderr)
    print(f"\n返回码: {result.returncode}")
except Exception as e:
    print(f"✗ 运行失败: {e}")
