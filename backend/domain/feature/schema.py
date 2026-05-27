"""
Feature Schema - 特征定义结构 (Domain 层)

核心概念：
- FeatureCategory: 特征分类
- FeatureValueType: 特征值类型
- FeatureDef: 特征定义（唯一真相源）

所有层必须引用这里的定义，不得自行创建类似结构。
"""

from typing import List, Optional
from dataclasses import dataclass
from enum import Enum


class FeatureCategory(str, Enum):
    """特征分类（数据源视角）"""
    RAW = "raw"
    TECHNICAL = "technical"
    DERIVATIVES = "derivatives"
    LIQUIDATION = "liquidation"
    ORDERBOOK = "orderbook"
    FLOW = "flow"
    MICROSTRUCTURE = "microstructure"
    CROSS_MARKET = "cross_market"
    COMPOSITE = "composite"


class AlphaFamily(str, Enum):
    """Alpha Family（alpha 研究视角的分类）

    Taxonomy:
    - PRICE_ACTION:  价格收益、回撤、结构
    - VOLATILITY:    波动率相关
    - FUNDING:       资金费率情绪
    - VOLUME:        成交量参与度
    - OPEN_INTEREST: 持仓量 / 杠杆结构
    - ORDER_FLOW:    主动买卖流 / taker flow
    - LIQUIDITY:     盘口深度 / 价差 / 流动性
    - CROSS_SECTIONAL: 跨币种截面 alpha
    - REGIME:        市场状态 / regime
    - EVENT_DRIVEN:  事件驱动（爆仓、funding spike 等）
    """
    PRICE_ACTION = "price_action"
    VOLATILITY = "volatility"
    FUNDING = "funding"
    VOLUME = "volume"
    OPEN_INTEREST = "open_interest"
    ORDER_FLOW = "order_flow"
    LIQUIDITY = "liquidity"
    CROSS_SECTIONAL = "cross_sectional"
    REGIME = "regime"
    EVENT_DRIVEN = "event_driven"


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
    alpha_family: Optional[AlphaFamily] = None
    
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
