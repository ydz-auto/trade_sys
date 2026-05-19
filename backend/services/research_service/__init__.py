"""
市场行为研究服务 - 入口模块
"""

from .market_behavior_research import (
    MarketBehaviorResearchSystem,
    EventDetector,
    OutcomeLabeler,
    DurationStatistics,
    MarketPlaybookGenerator,
    EventType,
    MarketState,
    MarketEvent,
    MarketPlaybook,
    run_market_behavior_analysis,
)

__all__ = [
    "MarketBehaviorResearchSystem",
    "EventDetector",
    "OutcomeLabeler",
    "DurationStatistics",
    "MarketPlaybookGenerator",
    "EventType",
    "MarketState",
    "MarketEvent",
    "MarketPlaybook",
    "run_market_behavior_analysis",
]
