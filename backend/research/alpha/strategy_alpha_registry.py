"""
Strategy Alpha Registry - Alpha 源定义注册表

将每个策略拆解为 alpha source 组件，声明式定义：
- 哪些 feature 构成 alpha
- 信号方向映射
- 组合逻辑
- 当前状态（active/blocked）

优先级：
  第一梯队: ret_1, ret_3, ret_5, ret_10, volume_zscore, volatility_zscore, range_pct, atr_expansion
  第二梯队: funding_zscore, trend_20, drawdown_from_high
  第三梯队: OI/liquidation (blocked, 待数据)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class AlphaDefinition:
    name: str
    features: List[str]
    mode: str
    direction: str
    primary_feature: str
    signal_direction_map: Dict[str, str]
    combo_logic: Optional[str] = None
    status: str = "active"
    blocked_reason: Optional[str] = None


class AlphaRegistry:
    _registry: Dict[str, AlphaDefinition] = {}

    @classmethod
    def register(cls, defn: AlphaDefinition) -> None:
        cls._registry[defn.name] = defn

    @classmethod
    def get(cls, name: str) -> AlphaDefinition:
        if name not in cls._registry:
            raise KeyError(f"Unknown alpha: {name}. Available: {list(cls._registry.keys())}")
        return cls._registry[name]

    @classmethod
    def get_active(cls) -> List[AlphaDefinition]:
        return [d for d in cls._registry.values() if d.status == "active"]

    @classmethod
    def list_all(cls) -> List[AlphaDefinition]:
        return list(cls._registry.values())


# ============================================================
# 第一梯队：ret reversal family
# ============================================================

AlphaRegistry.register(AlphaDefinition(
    name="ret_1_reversal",
    features=["ret_1"],
    mode="reversal",
    direction="long",
    primary_feature="ret_1",
    signal_direction_map={"ret_1": "negative_means_long"},
))

AlphaRegistry.register(AlphaDefinition(
    name="ret_3_reversal",
    features=["ret_3"],
    mode="reversal",
    direction="long",
    primary_feature="ret_3",
    signal_direction_map={"ret_3": "negative_means_long"},
))

AlphaRegistry.register(AlphaDefinition(
    name="ret_5_reversal",
    features=["ret_5"],
    mode="reversal",
    direction="long",
    primary_feature="ret_5",
    signal_direction_map={"ret_5": "negative_means_long"},
))

AlphaRegistry.register(AlphaDefinition(
    name="ret_10_reversal",
    features=["ret_10"],
    mode="reversal",
    direction="long",
    primary_feature="ret_10",
    signal_direction_map={"ret_10": "negative_means_long"},
))

# ============================================================
# 第一梯队：exhaustion / panic
# ============================================================

AlphaRegistry.register(AlphaDefinition(
    name="volume_exhaustion",
    features=["volume_zscore"],
    mode="exhaustion",
    direction="long",
    primary_feature="volume_zscore",
    signal_direction_map={"volume_zscore": "positive_means_long"},
))

AlphaRegistry.register(AlphaDefinition(
    name="volatility_panic_reversal",
    features=["volatility_zscore"],
    mode="panic_reversal",
    direction="long",
    primary_feature="volatility_zscore",
    signal_direction_map={"volatility_zscore": "positive_means_long"},
))

AlphaRegistry.register(AlphaDefinition(
    name="range_exhaustion",
    features=["range_pct"],
    mode="exhaustion",
    direction="long",
    primary_feature="range_pct",
    signal_direction_map={"range_pct": "positive_means_long"},
))

AlphaRegistry.register(AlphaDefinition(
    name="atr_expansion_reversal",
    features=["atr_expansion"],
    mode="expansion_reversal",
    direction="long",
    primary_feature="atr_expansion",
    signal_direction_map={"atr_expansion": "positive_means_long"},
))

# ============================================================
# 第二梯队：combo / filter
# ============================================================

AlphaRegistry.register(AlphaDefinition(
    name="funding_extreme_reversal",
    features=["funding_zscore", "ret_5", "trend_20"],
    mode="combo_reversal",
    direction="long",
    primary_feature="funding_zscore",
    signal_direction_map={
        "funding_zscore": "negative_means_long",
        "ret_5": "negative_means_long",
        "trend_20": "negative_means_long",
    },
    combo_logic="primary_with_confirm",
))

AlphaRegistry.register(AlphaDefinition(
    name="trend_filter_long",
    features=["trend_20"],
    mode="filter",
    direction="long",
    primary_feature="trend_20",
    signal_direction_map={"trend_20": "negative_means_long"},
))

AlphaRegistry.register(AlphaDefinition(
    name="drawdown_dip_buying",
    features=["drawdown_from_high"],
    mode="dip_buying",
    direction="long",
    primary_feature="drawdown_from_high",
    signal_direction_map={"drawdown_from_high": "negative_means_long"},
))

AlphaRegistry.register(AlphaDefinition(
    name="drawdown_ret5_combo",
    features=["drawdown_from_high", "ret_5"],
    mode="combo_dip_buying",
    direction="long",
    primary_feature="drawdown_from_high",
    signal_direction_map={
        "drawdown_from_high": "negative_means_long",
        "ret_5": "negative_means_long",
    },
    combo_logic="all_must_trigger",
))

AlphaRegistry.register(AlphaDefinition(
    name="short_squeeze_simplified",
    features=["ret_5", "volume_zscore", "funding_zscore"],
    mode="squeeze_reversal",
    direction="long",
    primary_feature="ret_5",
    signal_direction_map={
        "ret_5": "negative_means_long",
        "volume_zscore": "positive_means_long",
        "funding_zscore": "negative_means_long",
    },
    combo_logic="all_must_trigger",
))

# ============================================================
# Tier 1 空头：Crowded Long Reversal
# ============================================================

AlphaRegistry.register(AlphaDefinition(
    name="crowded_long_reversal",
    features=["ret_5_percentile", "funding_zscore", "volume_spike_up"],
    mode="crowded_reversal",
    direction="short",
    primary_feature="ret_5_percentile",
    signal_direction_map={
        "ret_5_percentile": "positive_means_short",
        "funding_zscore": "positive_means_short",
        "volume_spike_up": "positive_means_short",
    },
    combo_logic="all_must_trigger",
))

AlphaRegistry.register(AlphaDefinition(
    name="parabolic_blowoff",
    features=["parabolic_ret_zscore", "volume_zscore", "volatility_spike"],
    mode="blowoff_top",
    direction="short",
    primary_feature="parabolic_ret_zscore",
    signal_direction_map={
        "parabolic_ret_zscore": "positive_means_short",
        "volume_zscore": "positive_means_short",
        "volatility_spike": "positive_means_short",
    },
    combo_logic="all_must_trigger",
))

# ============================================================
# Tier 2 空头：Failed Breakout / Trend Exhaustion
# ============================================================

AlphaRegistry.register(AlphaDefinition(
    name="failed_breakout",
    features=["new_high_60", "breakout_volume_decay", "upper_wick_pct"],
    mode="failed_breakout",
    direction="short",
    primary_feature="breakout_volume_decay",
    signal_direction_map={
        "new_high_60": "positive_means_short",
        "breakout_volume_decay": "positive_means_short",
        "upper_wick_pct": "positive_means_short",
    },
    combo_logic="all_must_trigger",
))

AlphaRegistry.register(AlphaDefinition(
    name="trend_exhaustion",
    features=["consecutive_green", "momentum_overheat", "distance_from_ma"],
    mode="exhaustion_short",
    direction="short",
    primary_feature="consecutive_green",
    signal_direction_map={
        "consecutive_green": "positive_means_short",
        "momentum_overheat": "positive_means_short",
        "distance_from_ma": "positive_means_short",
    },
    combo_logic="all_must_trigger",
))

# ============================================================
# Tier 1 空头单因子：Funding Trap
# ============================================================

AlphaRegistry.register(AlphaDefinition(
    name="funding_trap_short",
    features=["funding_zscore"],
    mode="funding_trap",
    direction="short",
    primary_feature="funding_zscore",
    signal_direction_map={
        "funding_zscore": "positive_means_short",
    },
))

AlphaRegistry.register(AlphaDefinition(
    name="distance_from_high_short",
    features=["distance_from_high"],
    mode="overbought_short",
    direction="short",
    primary_feature="distance_from_high",
    signal_direction_map={
        "distance_from_high": "positive_means_short",
    },
))

# ============================================================
# 第三梯队：blocked (待数据)
# ============================================================

AlphaRegistry.register(AlphaDefinition(
    name="oi_behavior",
    features=[],
    mode="pending",
    direction="both",
    primary_feature="",
    signal_direction_map={},
    status="blocked",
    blocked_reason="OI data not yet in feature matrix",
))

AlphaRegistry.register(AlphaDefinition(
    name="liquidation_reversal",
    features=[],
    mode="pending",
    direction="both",
    primary_feature="",
    signal_direction_map={},
    status="blocked",
    blocked_reason="Liquidation data not yet in feature matrix",
))
