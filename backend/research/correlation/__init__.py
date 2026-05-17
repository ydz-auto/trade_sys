"""
多数据源正负相关性评估模块

功能：
1. 数据准备 - 结构化信号 + 非结构化信号
2. 单变量分析 - 相关性、互信息、Granger因果
3. 多变量分析 - 回归、树模型、SHAP
4. LLM情感增强
5. 综合评分与可视化

对接：直接读取 feature_pipeline 输出的 feature table
"""

from .types import SignalDirection
from .analyzer import CorrelationAnalyzer, analyze_correlation
from .data_preparation import DataPreparation, FeatureMatrix
from .univariate_analysis import UnivariateAnalyzer
from .multivariate_analysis import MultivariateAnalyzer
from .llm_enhancement import LLMEnhancement
from .scoring import CorrelationScorer, SignalAssessment
from .visualization import CorrelationVisualizer
from .storage import CorrelationStorage, get_correlation_storage

__all__ = [
    "CorrelationAnalyzer",
    "analyze_correlation",
    "SignalDirection",
    "DataPreparation",
    "FeatureMatrix",
    "UnivariateAnalyzer",
    "MultivariateAnalyzer",
    "LLMEnhancement",
    "CorrelationScorer",
    "SignalAssessment",
    "CorrelationVisualizer",
    "CorrelationStorage",
    "get_correlation_storage",
]
