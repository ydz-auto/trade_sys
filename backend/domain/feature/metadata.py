"""
Feature Metadata - 特征元数据定义 (Domain 层)

特征分类和元数据的权威定义。
所有层（service/runtime/api）必须引用此处的定义，不得自行定义 FeatureCategory 或 FeatureMetadata。
"""

from typing import Optional, Dict
from dataclasses import dataclass, field
from enum import Enum


class FeatureCategory(str, Enum):
    RAW = "raw"
    DERIVED = "derived"
    MICROSTRUCTURE = "microstructure"
    CROSS_MARKET = "cross_market"
    EVENT = "event"


@dataclass
class FeatureMetadata:
    name: str
    name_en: str
    category: FeatureCategory
    description: str
    data_type: str = "float"
    normalization_range: Optional[tuple] = None
    zscore_window: int = 288
    is_factor: bool = False
    source: str = "internal"
    default_weight: float = 1.0
