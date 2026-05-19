"""
Strategy Service - 策略服务

业务逻辑：策略信号转换、决策生成
"""

from .handlers import StrategyHandler, get_strategy_handler
from .strategies import (
    StrategyType,
    ActionType,
    StrategySignal,
    BaseStrategy,
    RSIStrategy,
    MACDStrategy,
    PanicReversalStrategy,
    LongLiquidationBounceStrategy,
    VolumeClimaxFadeStrategy,
    WeakBounceShortStrategy,
    MultiStrategyOrchestrator,
    DynamicStrategySelector,
    create_default_strategies,
)
from .innovation_strategies import (
    LeveragedShortSqueezeStrategy,
    MicroRangeRipplesStrategy,
    CascadeFlipStrategy,
    FundingExhaustionTrapStrategy,
    MemeManiaRotationStrategy,
    SessionGapExploitStrategy,
    DeadCatEchoStrategy,
    LiquidityVacuumBreakoutStrategy,
    create_innovation_strategies,
    register_innovation_strategies,
    INNOVATION_STRATEGY_CONFIGS,
)
from .strategy_discovery import (
    StrategyDiscoveryEngine,
    DiscoveredPattern,
    AutoDiscoveredStrategy,
)

__all__ = [
    "StrategyHandler",
    "get_strategy_handler",
    "StrategyType",
    "ActionType",
    "StrategySignal",
    "BaseStrategy",
    "RSIStrategy",
    "MACDStrategy",
    "PanicReversalStrategy",
    "LongLiquidationBounceStrategy",
    "VolumeClimaxFadeStrategy",
    "WeakBounceShortStrategy",
    "MultiStrategyOrchestrator",
    "DynamicStrategySelector",
    "create_default_strategies",
    # 创新策略
    "LeveragedShortSqueezeStrategy",
    "MicroRangeRipplesStrategy",
    "CascadeFlipStrategy",
    "FundingExhaustionTrapStrategy",
    "MemeManiaRotationStrategy",
    "SessionGapExploitStrategy",
    "DeadCatEchoStrategy",
    "LiquidityVacuumBreakoutStrategy",
    "create_innovation_strategies",
    "register_innovation_strategies",
    "INNOVATION_STRATEGY_CONFIGS",
    # 策略发现
    "StrategyDiscoveryEngine",
    "DiscoveredPattern",
    "AutoDiscoveredStrategy",
]
