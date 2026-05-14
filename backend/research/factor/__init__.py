"""
Factor module - 因子模块

包含：
- registry: 因子注册表
- evaluator: 因子评估器
- generator: 自动因子生成器
- advanced: 高级因子 (情绪/链上/宏观)
- iteration: 因子迭代优化
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
    """获取全局因子注册表实例"""
    global _registry
    if _registry is None:
        _registry = FactorRegistry()
    return _registry


def get_factor_evaluator() -> FactorEvaluator:
    """获取全局因子评估器实例"""
    global _evaluator
    if _evaluator is None:
        _evaluator = FactorEvaluator()
    return _evaluator


__all__ = [
    # Registry
    "FactorRegistry",
    "FactorMetadata", 
    "FactorType",
    "FactorStatus",
    "get_factor_registry",
    
    # Evaluator
    "FactorEvaluator",
    "EvaluationMetrics",
    "EvaluationResult",
    "get_factor_evaluator",
    
    # Generator
    "AutoFactorGenerator",
    "GeneratedFactor",
    "auto_generate_factors",
    "generate_mock_data",
    "OperatorLibrary",
    "FactorTemplateLibrary",
    
    # Advanced
    "AdvancedFactorCalculator",
    "SentimentFactors",
    "OnChainFactors",
    "MacroFactors",
    "CompositeFactors",
    "SystemFactor",
    
    # Iteration
    "FactorParamOptimizer",
    "MultiFactorOptimizer",
    "FactorWeight",
    "FactorParams",
    "AutoFactorIteration",
    "IterationResult",
]
