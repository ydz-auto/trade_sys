"""
Feature Materializer Module - 特征物化层

收敛版架构：
- schema_registry: 6大Feature Group Schema管理
- feature_aligner: 时间对齐
- matrix_builder: 统一矩阵构建
"""

from domain.feature.materializer.schema_registry import (
    FeatureSchemaRegistry,
    FeatureSchema,
    FeatureCategory,
    get_schema_registry
)
from domain.feature.materializer.feature_aligner import (
    FeatureAligner,
    AlignedFeatureData
)
from domain.feature.materializer.matrix_builder import (
    UnifiedMatrixBuilder,
    UnifiedFeatureMatrix
)

__all__ = [
    "FeatureSchemaRegistry",
    "FeatureSchema",
    "FeatureCategory",
    "get_schema_registry",
    "FeatureAligner",
    "AlignedFeatureData",
    "UnifiedMatrixBuilder",
    "UnifiedFeatureMatrix",
]

