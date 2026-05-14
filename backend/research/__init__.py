"""
Research Module - 研究模块

Alpha Infrastructure 核心模块：
1. Factor Registry - 因子注册表
2. Feature Pipeline - 特征流水线
3. Factor Evaluator - 因子评估
4. Walk-Forward Engine - 滚动回测
5. Experiment Tracker - 实验追踪
6. Alpha Pipeline - Alpha 生产流水线
7. Derivatives Factors - 衍生品结构因子
8. AI Framework - AI辅助研究框架（含安全系统）
9. Event Memory - 事件记忆库
10. Alpha Lifecycle - Alpha生命周期管理
"""

from .factor import (
    FactorRegistry,
    FactorType,
    FactorStatus,
    FactorEvaluator,
    EvaluationMetrics,
    get_factor_registry,
    get_factor_evaluator,
)

from .pipeline import (
    FeaturePipeline,
    PipelineStage,
    PipelineConfig,
    FeatureSpec,
    LabelSpec,
    Trainset,
    get_feature_pipeline,
)

from .backtest import (
    WalkForwardEngine,
    WalkForwardReport,
    WindowConfig,
    WindowResult,
    get_walk_forward_engine,
)

from .experiment import (
    ExperimentTracker,
    ExperimentStatus,
    ExperimentType,
    ExperimentResult,
    HyperparameterTrial,
    get_experiment_tracker,
)

from .strategy import (
    AlphaPipeline,
    StrategyVersion,
    AlphaDeployment,
    DeploymentStatus,
    get_alpha_pipeline,
)

# 可选导入 - 如果有依赖缺失不会崩溃
try:
    from .ai_framework import (
        SafetyConstraints,
        ProposalValidator,
        ProposalManager,
        Proposal,
        ProposalType,
        ProposalStatus,
        create_llm_proposal,
        ConfidenceScore,
        ApprovalLevel,
        ValidationResult,
    )
    AI_FRAMEWORK_AVAILABLE = True
except ImportError:
    AI_FRAMEWORK_AVAILABLE = False

try:
    from .event.event_memory import (
        EventMemoryDatabase,
        EventMemory,
        StructuredEvent,
        MarketReaction,
        EventType,
        Sentiment,
        Urgency,
    )
    EVENT_MEMORY_AVAILABLE = True
except ImportError:
    EVENT_MEMORY_AVAILABLE = False

try:
    from .factor.derivatives import (
        DerivativesFactors,
        DerivativesMetrics,
    )
    DERIVATIVE_FACTORS_AVAILABLE = True
except ImportError:
    DERIVATIVE_FACTORS_AVAILABLE = False

try:
    from .alpha_lifecycle import (
        AlphaLifecycleManager,
        ProposalLifecycleStatus,
        RegimeType,
        RegimeValidationResult,
        ProposalLineage,
        DatasetVersion,
        FeatureLineage,
        ReplaySnapshotBinding,
        ResearchBudget,
    )
    ALPHA_LIFECYCLE_AVAILABLE = True
except ImportError:
    ALPHA_LIFECYCLE_AVAILABLE = False

__all__ = [
    "FactorRegistry",
    "FactorType",
    "FactorStatus",
    "FactorEvaluator",
    "EvaluationMetrics",
    "get_factor_registry",
    "get_factor_evaluator",
    "FeaturePipeline",
    "PipelineStage",
    "PipelineConfig",
    "FeatureSpec",
    "LabelSpec",
    "Trainset",
    "get_feature_pipeline",
    "WalkForwardEngine",
    "WalkForwardReport",
    "WindowConfig",
    "WindowResult",
    "get_walk_forward_engine",
    "ExperimentTracker",
    "ExperimentStatus",
    "ExperimentType",
    "ExperimentResult",
    "HyperparameterTrial",
    "get_experiment_tracker",
    "AlphaPipeline",
    "StrategyVersion",
    "AlphaDeployment",
    "DeploymentStatus",
    "get_alpha_pipeline",
]

if AI_FRAMEWORK_AVAILABLE:
    __all__ += [
        "SafetyConstraints",
        "ProposalValidator",
        "ProposalManager",
        "Proposal",
        "ProposalType",
        "ProposalStatus",
        "create_llm_proposal",
        "ConfidenceScore",
        "ApprovalLevel",
        "ValidationResult",
    ]

if EVENT_MEMORY_AVAILABLE:
    __all__ += [
        "EventMemoryDatabase",
        "EventMemory",
        "StructuredEvent",
        "MarketReaction",
        "EventType",
        "Sentiment",
        "Urgency",
    ]

if DERIVATIVE_FACTORS_AVAILABLE:
    __all__ += [
        "DerivativesFactors",
        "DerivativesMetrics",
    ]

if ALPHA_LIFECYCLE_AVAILABLE:
    __all__ += [
        "AlphaLifecycleManager",
        "ProposalLifecycleStatus",
        "RegimeType",
        "RegimeValidationResult",
        "ProposalLineage",
        "DatasetVersion",
        "FeatureLineage",
        "ReplaySnapshotBinding",
        "ResearchBudget",
    ]
