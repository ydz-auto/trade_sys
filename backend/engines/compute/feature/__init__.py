"""
Feature Module - 统一特征计算

包含：
- contracts: 特征接口定义
- registry: 特征注册中心
- cache: 特征缓存
- engine: 特征计算引擎
- technical: 技术指标特征
- basic: 基础特征
- market: 市场特征
- microstructure: 微观结构特征
- regime: 市场状态特征
- alpha_factors: Alpha因子
"""

from engines.compute.feature.contracts import (
    Feature,
    BaseFeature,
    TechnicalFeature,
    MarketFeature,
    MicrostructureFeature,
    RegimeFeature,
    CompositeFeature,
)

from engines.compute.feature.registry import (
    FeatureRegistry,
    get_registry,
)

from engines.compute.feature.cache import (
    FeatureCache,
    get_cache,
)

from engines.compute.feature.engine import (
    FeatureEngine,
    get_engine,
)

__all__ = [
    "Feature",
    "BaseFeature",
    "TechnicalFeature",
    "MarketFeature",
    "MicrostructureFeature",
    "RegimeFeature",
    "CompositeFeature",
    "FeatureRegistry",
    "get_registry",
    "FeatureCache",
    "get_cache",
    "FeatureEngine",
    "get_engine",
]
