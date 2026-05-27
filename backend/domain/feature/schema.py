"""
Feature Schema - 特征定义结构 (Domain 层)

核心概念：
- FeatureCategory: 特征分类
- FeatureValueType: 特征值类型
- FeatureDef: 特征定义（唯一真相源）

所有层必须引用这里的定义，不得自行创建类似结构。
"""

from typing import List
from dataclasses import dataclass
from enum import Enum


class FeatureCategory(str, Enum):
    """特征分类"""
    RAW = "raw"
    TECHNICAL = "technical"
    DERIVATIVES = "derivatives"
    LIQUIDATION = "liquidation"
    ORDERBOOK = "orderbook"
    FLOW = "flow"
    MICROSTRUCTURE = "microstructure"
    CROSS_MARKET = "cross_market"
    COMPOSITE = "composite"


class FeatureValueType(str, Enum):
    """特征值类型"""
    FLOAT = "float"
    INT = "int"
    STRING = "string"
    BOOL = "bool"
    LIST = "list"
    TUPLE = "tuple"


@dataclass(frozen=True)
class FeatureDef:
    """
    特征定义（唯一真相源）
    
    核心原则：
    - 所有特征必须在这里定义
    - 名称、类型、周期、依赖在此统一管理
    - 不包含计算逻辑（仅定义）
    """
    name: str
    category: FeatureCategory
    value_type: FeatureValueType
    default_timeframes: List[str]
    required_sources: List[str]
    description: str
    
    def __post_init__(self):
        """验证字段完整性"""
        if not self.name:
            raise ValueError("Feature name cannot be empty")
        if not self.description:
            raise ValueError("Feature description cannot be empty")
    
    @property
    def is_timeframe_specific(self) -> bool:
        """是否是时间周期相关特征"""
        return len(self.default_timeframes) > 0
    
    @property
    def has_dependencies(self) -> bool:
        """是否有依赖的数据源"""
        return len(self.required_sources) > 0
