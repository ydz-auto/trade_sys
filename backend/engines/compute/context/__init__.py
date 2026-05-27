"""
MarketContext 模块

核心职责：
1. 定义 MarketContext 的固定 schema
2. 提供从 raw features 到 MarketContext 的构建器
3. 管理特征到上下文的映射关系
4. 验证上下文数据完整性
5. 防止未来信息泄漏

数据流：
raw data → features_by_tf → MarketContextBuilder → MarketContext → StrategyV2
"""

from .schema import (
    TrendState,
    MomentumDirection,
    VolatilityState,
    VolumeState,
    FlowPressure,
    LiquidityState,
    FundingBias,
    PriceState,
    TrendStateData,
    MomentumState,
    VolatilityStateData,
    VolumeStateData,
    FlowState,
    LiquidityStateData,
    TimeframeContext,
    OIData,
    FundingData,
    LiquidationData,
    DerivativesContext,
    CrossMarketData,
    RiskContext,
    STANDARD_TIMEFRAMES,
    MarketContext,
)

from .builder import MarketContextBuilder
from .feature_map import CONTEXT_FEATURE_MAP, get_required_features, validate_context_path
from .validators import ContextValidationError, MarketContextValidator, validate_strategy_requirements
from .leakage_guard import (
    FutureLeakageError,
    FORBIDDEN_PATTERNS,
    LeakageGuardMode,
    ContextLeakageGuard,
    create_guard,
)


__all__ = [
    # 枚举类型
    "TrendState",
    "MomentumDirection",
    "VolatilityState",
    "VolumeState",
    "FlowPressure",
    "LiquidityState",
    "FundingBias",
    
    # 状态类
    "PriceState",
    "TrendStateData",
    "MomentumState",
    "VolatilityStateData",
    "VolumeStateData",
    "FlowState",
    "LiquidityStateData",
    "TimeframeContext",
    
    # 跨周期上下文
    "OIData",
    "FundingData",
    "LiquidationData",
    "DerivativesContext",
    "CrossMarketData",
    "RiskContext",
    
    # 主上下文
    "STANDARD_TIMEFRAMES",
    "MarketContext",
    
    # 构建器
    "MarketContextBuilder",
    
    # 特征映射
    "CONTEXT_FEATURE_MAP",
    "get_required_features",
    "validate_context_path",
    
    # 验证器
    "ContextValidationError",
    "MarketContextValidator",
    "validate_strategy_requirements",
    
    # 防泄漏
    "FutureLeakageError",
    "FORBIDDEN_PATTERNS",
    "LeakageGuardMode",
    "ContextLeakageGuard",
    "create_guard",
]
