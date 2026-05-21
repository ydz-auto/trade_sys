"""
Feature Discovery Lab - 特征发现实验室

这是一个研究模块，用于特征发现、评估和迭代优化。

重要：这不是 runtime truth，只是研究辅助工具。
真正的 runtime truth 在 domain/feature/ 和 domain/feature/matrix/。

包含：
- registry: 特征注册表
- evaluator: 特征评估器
- generator: 自动特征生成器
- advanced: 高级特征（情绪/链上/宏观）
- iteration: 特征迭代优化
- llm_generator: LLM辅助生成
"""

from research.factor.registry import FactorRegistry, FactorMetadata, FactorType, FactorStatus
from research.factor.evaluator import FactorEvaluator, EvaluationMetrics, EvaluationResult
from research.factor.generator import (
    AutoFactorGenerator,
    GeneratedFactor,
    auto_generate_factors,
    generate_mock_data,
    OperatorLibrary,
    FactorTemplateLibrary
)
from research.factor.advanced import (
    AdvancedFactorCalculator,
    SentimentFactors,
    OnChainFactors,
    MacroFactors,
    CompositeFactors,
    SystemFactor
)
from research.factor.iteration import (
    FactorParamOptimizer,
    MultiFactorOptimizer,
    FactorWeight,
    FactorParams,
    AutoFactorIteration,
    IterationResult
)

_registry = None
_evaluator = None


def get_factor_registry() -> FactorRegistry:
    """获取全局特征注册表实例"""
    global _registry
    if _registry is None:
        _registry = FactorRegistry()
    return _registry


def get_factor_evaluator() -> FactorEvaluator:
    """获取全局特征评估器实例"""
    global _evaluator
    if _evaluator is None:
        _evaluator = FactorEvaluator()
    return _evaluator


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
