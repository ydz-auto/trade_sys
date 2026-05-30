"""
Alpha Features Module

特征计算和管理模块

迁移的文件：
- feature_matrix.py -> matrix.py
- feature_availability_audit.py -> availability.py
- data_quality_check.py -> quality.py
- features_short/ -> short_features.py
"""

from research.alpha.features.matrix import (
    build_feature_matrix,
)

from research.alpha.features.matrix_adapter import (
    get_research_feature_matrix,
)

__all__ = [
    "build_feature_matrix",
    "get_research_feature_matrix",
]
