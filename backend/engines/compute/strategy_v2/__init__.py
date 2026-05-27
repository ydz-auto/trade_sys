"""
Strategy V2 Module - 策略 V2 模块

核心设计原则：
1. 策略只接收 MarketContext，不直接读 features
2. 每个策略必须声明 StrategyMeta
3. 信号生成遵循固定流程：过滤 → 判断 → 计算置信度

数据流：
MarketContext → StrategyV2 → Signal

主要组件：
- StrategyMeta: 策略元数据定义
- StrategyV2: 策略基类
- Signal: 信号类
- StrategyRegistry: 策略注册表
- 5 个核心策略实现
"""

from .metadata import StrategyMeta, STRATEGY_TAGS
from .base import SignalType, Signal, StrategyV2, combine_signals
from .registry import StrategyRegistry, register_strategy
from .strategies import (
    OpenInterestBehaviorStrategy,
    FundingExtremeReversalStrategy,
    LiquidationCascadeStrategy,
    ShortSqueezeStrategy,
    TradePressureBounceStrategy,
)


__all__ = [
    # 元数据
    "StrategyMeta",
    "STRATEGY_TAGS",
    
    # 基础类
    "SignalType",
    "Signal",
    "StrategyV2",
    "combine_signals",
    
    # 注册表
    "StrategyRegistry",
    "register_strategy",
    
    # 策略实现
    "OpenInterestBehaviorStrategy",
    "FundingExtremeReversalStrategy",
    "LiquidationCascadeStrategy",
    "ShortSqueezeStrategy",
    "TradePressureBounceStrategy",
]
