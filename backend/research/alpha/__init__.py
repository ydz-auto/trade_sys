"""
Alpha Research Pipeline

Feature → Label → IC → Regime → Strategy

模块:
- labels.py: 未来收益标签 (future_ret, MFE, MAE)
- feature_matrix.py: 特征矩阵构建
- regime_analysis.py: 市场环境分类 (trend/vol regime)
- ic_analysis.py: IC/Rank IC 分析
"""

from research.alpha.labels import compute_labels
from research.alpha.feature_matrix import build_feature_matrix, build_feature_matrix_from_df
from research.alpha.regime_analysis import classify_regime
from research.alpha.ic_analysis import compute_ic_table

__all__ = [
    "compute_labels",
    "build_feature_matrix",
    "build_feature_matrix_from_df",
    "classify_regime",
    "compute_ic_table",
]
