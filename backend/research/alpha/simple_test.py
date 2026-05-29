"""最简单的测试：避开GPU和复杂逻辑，只验证策略注册表"""
import sys
from pathlib import Path
BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# 先打印Python信息
print(f"Python: {sys.executable}")
print(f"Path: {sys.path[:3]}")

print("\n" + "=" * 60)
print("Step 1: 测试策略注册表")
print("=" * 60)

# 只导入策略注册表，避开feature_matrix等复杂模块
from research.alpha.strategy_alpha_registry import AlphaRegistry

short_strategies = [s for s in AlphaRegistry.get_active() if s.direction == "short"]
print(f"✓ 找到 {len(short_strategies)} 个空头策略:")
for s in short_strategies:
    print(f"  - {s.name}")
    print(f"    features: {s.features}")
    print(f"    mode: {s.mode}")
    print(f"    signal_direction_map: {s.signal_direction_map}")

print("\n" + "=" * 60)
print("Step 2: 重点检查优先测试的6个策略")
print("=" * 60)

priorities = [
    "crowded_long_reversal",
    "parabolic_blowoff", 
    "failed_breakout",
    "trend_exhaustion",
    "funding_trap_short",
    "distance_from_high_short"
]

print("优先测试的6个空头策略:")
all_found = True
for name in priorities:
    try:
        strat = AlphaRegistry.get(name)
        print(f"  ✓ {name}")
    except Exception as e:
        print(f"  ✗ {name}: {e}")
        all_found = False

if all_found:
    print("\n✓ 所有6个优先策略都已注册")
else:
    print("\n✗ 有策略缺失")

print("\n" + "=" * 60)
print("Step 3: 检查 pipeline 的 --direction 参数")
print("=" * 60)

import argparse
from research.alpha.pipeline import main
# 检查 pipeline 中的 argparse 设置
import importlib.util
spec = importlib.util.spec_from_file_location("pipeline", str(BACKEND_ROOT / "research" / "alpha" / "pipeline.py"))
pipeline = importlib.util.module_from_spec(spec)

# 模拟读取到 pipeline 的 parser 部分
with open(BACKEND_ROOT / "research" / "alpha" / "pipeline.py", encoding="utf-8") as f:
    content = f.read()
    
has_direction = "--direction" in content
print(f"✓ pipeline 包含 --direction 参数: {has_direction}")

print("\n测试完成!")
