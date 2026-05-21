"""
Schema Registry - 特征Schema注册中心

核心功能：
- 定义6大Feature Group的标准化Schema
- Feature描述符管理
- Feature版本控制
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum


class FeatureCategory(Enum):
    """6大特征类别"""
    MARKET = "market"
    TRADE = "trade"
    DERIVATIVES = "derivatives"
    LIQUIDATION = "liquidation"
    MICROSTRUCTURE = "microstructure"
    NARRATIVE = "narrative"
    REGIME = "regime"


@dataclass
class FeatureSchema:
    """特征Schema
    包含时间纪律信息，防止数据泄漏
    """
    name: str
    category: FeatureCategory
    description: str
    data_type: str = "float"
    is_required: bool = False
    default_value: float = 0.0
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    version: str = "1.0"
    
    # 时间纪律字段
    available_after_periods: int = 0  # 需要等待多少个周期后才能使用该特征
    requires_lookback: bool = False  # 是否需要历史数据计算
    lookback_window: int = 0  # 回溯窗口大小（周期数）
    is_future_derived: bool = False  # 是否由未来数据派生（需要特别小心）


class FeatureSchemaRegistry:
    """特征Schema注册中心"""
    
    def __init__(self):
        self._schemas: Dict[str, FeatureSchema] = {}
        self._register_default_schemas()
    
    def _register_default_schemas(self):
        """注册默认6大特征组
        包含时间纪律信息，防止数据泄漏
        """
        
        # Market Features
        self._register(FeatureSchema("return_1m", FeatureCategory.MARKET, "1分钟收益率", "float", True, requires_lookback=False, lookback_window=1))
        self._register(FeatureSchema("volatility_1m", FeatureCategory.MARKET, "1分钟已实现波动率", "float", True, requires_lookback=True, lookback_window=20))
        self._register(FeatureSchema("momentum_5m", FeatureCategory.MARKET, "5分钟动量", "float", requires_lookback=True, lookback_window=5))
        self._register(FeatureSchema("atr", FeatureCategory.MARKET, "平均真实波幅", "float", requires_lookback=True, lookback_window=14))
        self._register(FeatureSchema("volume_spike", FeatureCategory.MARKET, "成交量尖峰", "float", requires_lookback=True, lookback_window=20))
        
        # Trade Flow Features
        self._register(FeatureSchema("trade_delta", FeatureCategory.TRADE, "主动买卖差", "float", True, requires_lookback=False))
        self._register(FeatureSchema("cumulative_delta", FeatureCategory.TRADE, "累积主动流", "float", True, requires_lookback=True, lookback_window=60))
        self._register(FeatureSchema("aggressive_buy_ratio", FeatureCategory.TRADE, "主动买占比", "float", True, requires_lookback=False))
        self._register(FeatureSchema("sweep_score", FeatureCategory.TRADE, "扫单分数", "float", True, requires_lookback=False))
        self._register(FeatureSchema("large_trade_ratio", FeatureCategory.TRADE, "大单占比", "float", requires_lookback=False))
        self._register(FeatureSchema("trade_velocity", FeatureCategory.TRADE, "成交速度", "float", requires_lookback=False))
        self._register(FeatureSchema("ofi", FeatureCategory.TRADE, "订单流不平衡", "float", requires_lookback=False))
        
        # Derivatives Features
        self._register(FeatureSchema("oi_delta", FeatureCategory.DERIVATIVES, "持仓量变化", "float", True, requires_lookback=False))
        self._register(FeatureSchema("oi_zscore", FeatureCategory.DERIVATIVES, "持仓量Z-score", "float", True, requires_lookback=True, lookback_window=240, available_after_periods=1))
        self._register(FeatureSchema("funding_zscore", FeatureCategory.DERIVATIVES, "资金费率Z-score", "float", True, requires_lookback=True, lookback_window=240, available_after_periods=1))
        self._register(FeatureSchema("leverage_crowdedness", FeatureCategory.DERIVATIVES, "杠杆拥挤度", "float", True, requires_lookback=True, lookback_window=240, available_after_periods=1))
        self._register(FeatureSchema("squeeze_probability", FeatureCategory.DERIVATIVES, "挤压概率", "float", requires_lookback=True, lookback_window=24, available_after_periods=1))
        self._register(FeatureSchema("long_short_imbalance", FeatureCategory.DERIVATIVES, "多空失衡", "float", requires_lookback=False))
        
        # Liquidation Features
        self._register(FeatureSchema("liquidation_cluster", FeatureCategory.LIQUIDATION, "爆仓聚集", "float", True, requires_lookback=False))
        self._register(FeatureSchema("chain_probability", FeatureCategory.LIQUIDATION, "连锁概率", "float", requires_lookback=True, lookback_window=30, available_after_periods=1))
        self._register(FeatureSchema("panic_score", FeatureCategory.LIQUIDATION, "恐慌分数", "float", requires_lookback=True, lookback_window=10, available_after_periods=1))
        self._register(FeatureSchema("reversal_probability", FeatureCategory.LIQUIDATION, "反转概率", "float", requires_lookback=True, lookback_window=30, is_future_derived=False, available_after_periods=1))
        
        # Microstructure Features
        self._register(FeatureSchema("imbalance_5", FeatureCategory.MICROSTRUCTURE, "5档失衡", "float", True, requires_lookback=False))
        self._register(FeatureSchema("spread", FeatureCategory.MICROSTRUCTURE, "价差", "float", True, requires_lookback=False))
        self._register(FeatureSchema("liquidity_shift", FeatureCategory.MICROSTRUCTURE, "流动性转移", "float", requires_lookback=True, lookback_window=10, available_after_periods=1))
        self._register(FeatureSchema("wall_score", FeatureCategory.MICROSTRUCTURE, "墙分数", "float", requires_lookback=False))
        
        # Narrative Features
        self._register(FeatureSchema("news_sentiment", FeatureCategory.NARRATIVE, "新闻情绪", "float", True, requires_lookback=False, available_after_periods=1))
        self._register(FeatureSchema("twitter_velocity", FeatureCategory.NARRATIVE, "推特速度", "float", True, requires_lookback=False, available_after_periods=1))
        self._register(FeatureSchema("narrative_strength", FeatureCategory.NARRATIVE, "叙事强度", "float", True, requires_lookback=True, lookback_window=24, available_after_periods=1))
        
        # Regime Features
        self._register(FeatureSchema("volatility_regime", FeatureCategory.REGIME, "波动体制", "float", True, requires_lookback=True, lookback_window=60, available_after_periods=1))
        self._register(FeatureSchema("trend_regime", FeatureCategory.REGIME, "趋势体制", "float", requires_lookback=True, lookback_window=20, available_after_periods=1))
        self._register(FeatureSchema("liquidity_regime", FeatureCategory.REGIME, "流动性体制", "float", requires_lookback=True, lookback_window=30, available_after_periods=1))
        self._register(FeatureSchema("leverage_regime", FeatureCategory.REGIME, "杠杆体制", "float", requires_lookback=True, lookback_window=60, available_after_periods=1))
    
    def _register(self, schema: FeatureSchema):
        self._schemas[schema.name] = schema
    
    def get_schema(self, name: str) -> Optional[FeatureSchema]:
        return self._schemas.get(name)
    
    def get_all_schemas(self) -> List[FeatureSchema]:
        return list(self._schemas.values())
    
    def get_schemas_by_category(self, category: FeatureCategory) -> List[FeatureSchema]:
        return [s for s in self._schemas.values() if s.category == category]
    
    def get_required_features(self) -> List[str]:
        return [s.name for s in self._schemas.values() if s.is_required]
    
    def get_all_feature_names(self) -> List[str]:
        return list(self._schemas.keys())


_schema_registry = None


def get_schema_registry() -> FeatureSchemaRegistry:
    global _schema_registry
    if _schema_registry is None:
        _schema_registry = FeatureSchemaRegistry()
    return _schema_registry

