"""
Feature Domain Module - 特征领域模块

唯一真相源定义在此，所有地方引用特征必须从此模块获取。

导出：
- schema: FeatureDef, FeatureCategory, FeatureValueType
- registry: FEATURE_REGISTRY, get_feature_def, is_feature_registered
- aliases: FEATURE_ALIASES, normalize_feature_name
- availability: SystematicAvailabilityGuard, get_systematic_guard
"""

from .schema import (
    FeatureDef,
    FeatureCategory,
    FeatureValueType,
)

from .registry import (
    FEATURE_REGISTRY,
    get_feature_def,
    is_feature_registered,
    list_features_by_category,
    list_all_feature_names,
)

from .aliases import (
    FEATURE_ALIASES,
    normalize_feature_name,
    get_original_names,
)

from .availability import (
    SystematicAvailabilityGuard,
    get_systematic_guard,
    AvailabilityStatus,
    FeatureRule,
)

__all__ = [
    # Schema
    "FeatureDef",
    "FeatureCategory",
    "FeatureValueType",
    # Registry
    "FEATURE_REGISTRY",
    "get_feature_def",
    "is_feature_registered",
    "list_features_by_category",
    "list_all_feature_names",
    # Aliases
    "FEATURE_ALIASES",
    "normalize_feature_name",
    "get_original_names",
    # Availability
    "SystematicAvailabilityGuard",
    "get_systematic_guard",
    "AvailabilityStatus",
    "FeatureRule",
]
