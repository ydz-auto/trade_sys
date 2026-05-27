"""
Strategy Calculators - 无状态策略计算模块

所有策略的纯计算逻辑，不包含状态管理。
状态由 runtime 层管理。
"""
# 基础技术指标计算器
from .rsi_calculator import calculate_rsi_signal
from .macd_calculator import calculate_macd_signal
from .trend_calculator import calculate_trend_following_signal
from .bollinger_calculator import calculate_bb_compression_signal

# 行为策略计算器
from .behavioral_calculators import (
    calculate_panic_reversal,
    calculate_oi_flush,
    calculate_short_squeeze,
    calculate_funding_exhaustion_trap,
    calculate_dead_cat_echo,
)

# 微观结构策略计算器
from .microstructure_calculators import (
    calculate_imbalance_pressure,
    calculate_sweep_detection,
    calculate_liquidity_vacuum,
    calculate_aggressive_flow,
    calculate_volume_climax_fade,
    calculate_weak_bounce_short,
)

# 技术策略计算器
from .technical_calculators import (
    calculate_breakout,
    calculate_volatility_expansion,
    calculate_momentum_ignition,
    calculate_sma_crossover,
    calculate_ema_crossover,
    calculate_bollinger_bands,
    calculate_momentum,
)

# 跨交易所计算器
from .arbitrage_calculators import (
    calculate_lead_lag,
    calculate_premium_divergence,
)

__all__ = [
    # 基础技术指标
    "calculate_rsi_signal",
    "calculate_macd_signal",
    "calculate_trend_following_signal",
    "calculate_bb_compression_signal",
    
    # 行为策略
    "calculate_panic_reversal",
    "calculate_oi_flush",
    "calculate_short_squeeze",
    "calculate_funding_exhaustion_trap",
    "calculate_dead_cat_echo",
    
    # 微观结构策略
    "calculate_imbalance_pressure",
    "calculate_sweep_detection",
    "calculate_liquidity_vacuum",
    "calculate_aggressive_flow",
    "calculate_volume_climax_fade",
    "calculate_weak_bounce_short",
    
    # 技术策略
    "calculate_breakout",
    "calculate_volatility_expansion",
    "calculate_momentum_ignition",
    "calculate_sma_crossover",
    "calculate_ema_crossover",
    "calculate_bollinger_bands",
    "calculate_momentum",
    
    # 跨交易所
    "calculate_lead_lag",
    "calculate_premium_divergence",
]
