"""
Alpha Research Pipeline

Feature -> Label -> IC -> Regime -> Strategy

模块:
- labels.py: 未来收益标签 (future_ret, MFE, MAE)
- feature_matrix.py: 特征矩阵构建
- regime_analysis.py: 市场环境分类 (trend/vol regime)
- ic_analysis.py: IC/Rank IC 分析
- strategy_alpha_registry.py: Alpha 源定义注册表
- alpha_signal_strategy.py: Feature-level 到 Strategy-level 桥接
- pipeline.py: Alpha Factory 7 阶段验证流水线
- leaderboard.py: 结果聚合与输出
"""

from research.alpha.labels import compute_labels
from research.alpha.feature_matrix import build_feature_matrix, build_feature_matrix_from_df
from research.alpha.regime_analysis import classify_regime
from research.alpha.ic_analysis import compute_ic_table
from research.alpha.strategy_alpha_registry import AlphaRegistry, AlphaDefinition
from research.alpha.pipeline import AlphaPipeline, AlphaPipelineResult, AlphaValidationResult
from research.alpha.leaderboard import Leaderboard

__all__ = [
    "compute_labels",
    "build_feature_matrix",
    "build_feature_matrix_from_df",
    "classify_regime",
    "compute_ic_table",
    "AlphaRegistry",
    "AlphaDefinition",
    "AlphaPipeline",
    "AlphaPipelineResult",
    "AlphaValidationResult",
    "Leaderboard",
]
