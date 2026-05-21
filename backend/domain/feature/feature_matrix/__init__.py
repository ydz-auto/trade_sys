"""
Feature Matrix Module - 特征矩阵模块

核心功能：
- 基于6大Feature Group的统一特征矩阵
- 支持历史和实时模式
- 与materializer层集成
"""

from domain.feature.feature_matrix.feature_matrix import (
    get_historical_feature_matrix,
    get_available_features,
    save_unified_matrix,
    load_unified_matrix
)

__all__ = [
    "get_historical_feature_matrix",
    "get_available_features",
    "save_unified_matrix",
    "load_unified_matrix"
]
