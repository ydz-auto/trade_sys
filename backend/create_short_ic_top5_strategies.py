"""
基于 Short IC Top5 特征创建策略定义
"""
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from research.alpha.strategy_alpha_registry import AlphaRegistry, AlphaDefinition


# 先检查是否已注册
existing_strategies = [s.name for s in AlphaRegistry.get_active()]

# 基于 IC Top5 的 Short 策略
short_ic_strategies = [
    # 1. volume_climax_short - 放天量冲顶后做空
    AlphaDefinition(
        name="volume_climax_short",
        features=["volume_climax", "volume_zscore"],
        mode="volume_climax_short",
        direction="short",
        primary_feature="volume_climax",
        signal_direction_map={
            "volume_climax": "positive_means_short",
            "volume_zscore": "positive_means_short",
        },
        combo_logic="primary_with_confirm",
    ),
    
    # 2. double_top_short - 双顶形态做空
    AlphaDefinition(
        name="double_top_short",
        features=["double_top_probability"],
        mode="double_top_short",
        direction="short",
        primary_feature="double_top_probability",
        signal_direction_map={
            "double_top_probability": "positive_means_short",
        },
        combo_logic=None,
    ),
    
    # 3. momentum_divergence_short - 动量背离做空
    AlphaDefinition(
        name="momentum_divergence_short",
        features=["momentum_divergence", "ret_5"],
        mode="momentum_divergence_short",
        direction="short",
        primary_feature="momentum_divergence",
        signal_direction_map={
            "momentum_divergence": "positive_means_short",
            "ret_5": "positive_means_short",
        },
        combo_logic="primary_with_confirm",
    ),
    
    # 4. new_high_failure_short - 创新高后失败做空
    AlphaDefinition(
        name="new_high_failure_short",
        features=["new_high_60", "breakout_volume_decay"],
        mode="new_high_failure_short",
        direction="short",
        primary_feature="new_high_60",
        signal_direction_map={
            "new_high_60": "positive_means_short",
            "breakout_volume_decay": "positive_means_short",
        },
        combo_logic="all_must_trigger",
    ),
    
    # 5. trend_overextended_short - 趋势过度延伸做空
    AlphaDefinition(
        name="trend_overextended_short",
        features=["trend_20", "ret_10"],
        mode="trend_overextended_short",
        direction="short",
        primary_feature="trend_20",
        signal_direction_map={
            "trend_20": "positive_means_short",
            "ret_10": "positive_means_short",
        },
        combo_logic="primary_with_confirm",
    ),
]


for strategy in short_ic_strategies:
    if strategy.name in existing_strategies:
        print(f"跳过已存在的策略: {strategy.name}")
        continue
    
    AlphaRegistry.register(strategy)
    print(f"已注册策略: {strategy.name}")

print(f"\n总共注册了 {len(short_ic_strategies)} 个新策略")
print(f"活跃策略总数: {len(AlphaRegistry.get_active())}")
