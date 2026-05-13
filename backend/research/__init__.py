"""
Research Module - 研究模块

Alpha Infrastructure 核心模块：
1. Factor Registry - 因子注册表
2. Feature Pipeline - 特征流水线
3. Factor Evaluator - 因子评估
4. Walk-Forward Engine - 滚动回测
5. Experiment Tracker - 实验追踪
6. Alpha Pipeline - Alpha 生产流水线
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
