"""
Factor module - 因子模块（已废弃）

重要：这个模块已经重定位为 research/feature_lab/

因子本质上是 "Feature Discovery Lab"，不是 runtime truth。
真正的 runtime truth 在 domain/feature/ 和 domain/feature/matrix/。

请使用：
    from research.feature_lab import *

迁移说明：
- 所有因子功能现在在 research/feature_lab/
- domain/feature/ 包含真正的 runtime 特征
- domain/feature/matrix/ 包含 Feature Matrix（中央真相层）
"""

from research.feature_lab import *

__all__ = [
    "FactorRegistry",
    "FactorMetadata",
    "FactorType",
    "FactorStatus",
    "get_factor_registry",
    "FactorEvaluator",
    "EvaluationMetrics",
    "EvaluationResult",
    "get_factor_evaluator",
    "AutoFactorGenerator",
    "GeneratedFactor",
    "auto_generate_factors",
    "generate_mock_data",
    "OperatorLibrary",
    "FactorTemplateLibrary",
    "AdvancedFactorCalculator",
    "SentimentFactors",
    "OnChainFactors",
    "MacroFactors",
    "CompositeFactors",
    "SystemFactor",
    "FactorParamOptimizer",
    "MultiFactorOptimizer",
    "FactorWeight",
    "FactorParams",
    "AutoFactorIteration",
    "IterationResult",
]
