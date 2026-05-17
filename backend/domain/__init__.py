"""
Domain Package - 核心业务领域

包含：
- Validation Boundary: Research → Runtime 隔离层
- Portfolio Projection: 持仓状态持久化
- Timeframe Coordinator: 多周期协调
- Replay Engine: 事件回放引擎
- Observability: 运行时可观测性
- Narrative Engine: AI 解释层
"""

from .validation_boundary import (
    ValidationBoundary,
    ValidationStage,
    ValidationResult,
    ValidationCriteria,
    ValidationReport,
    ApprovedSignal,
    DeployedFactor,
    get_validation_boundary,
)

from .portfolio_projection import (
    PortfolioProjection,
    Position,
    PositionSide,
    PositionSnapshot,
    get_portfolio_projection,
)

from .timeframe_coordinator import (
    TimeframeCoordinator,
    Timeframe,
    RegimeType,
    SignalAlignment,
    TimeframeSignal,
    CoordinatedSignal,
    RegimeHierarchy,
    get_timeframe_coordinator,
)

from .replay_engine import (
    ReplayEngine,
    ReplayMode,
    ReplayStatus,
    ReplayConfig,
    ReplayState,
    ReplayEvent,
    get_replay_engine,
)

from .observability import (
    RuntimeMetrics,
    MetricType,
    MetricValue,
    Alert,
    get_runtime_metrics,
)

from .narrative_engine import (
    NarrativeEngine,
    NarrativeType,
    Confidence,
    Narrative,
    DecisionExplanation,
    SignalNarrative,
    get_narrative_engine,
)

__all__ = [
    "ValidationBoundary",
    "ValidationStage",
    "ValidationResult",
    "ValidationCriteria",
    "ValidationReport",
    "ApprovedSignal",
    "DeployedFactor",
    "get_validation_boundary",
    "PortfolioProjection",
    "Position",
    "PositionSide",
    "PositionSnapshot",
    "get_portfolio_projection",
    "TimeframeCoordinator",
    "Timeframe",
    "RegimeType",
    "SignalAlignment",
    "TimeframeSignal",
    "CoordinatedSignal",
    "RegimeHierarchy",
    "get_timeframe_coordinator",
    "ReplayEngine",
    "ReplayMode",
    "ReplayStatus",
    "ReplayConfig",
    "ReplayState",
    "ReplayEvent",
    "get_replay_engine",
    "RuntimeMetrics",
    "MetricType",
    "MetricValue",
    "Alert",
    "get_runtime_metrics",
    "NarrativeEngine",
    "NarrativeType",
    "Confidence",
    "Narrative",
    "DecisionExplanation",
    "SignalNarrative",
    "get_narrative_engine",
]
