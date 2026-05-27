"""
特征配置类型
Feature Configuration Types

定义特征计算所需的配置，确保特征计算的一致性和可重现性。
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Set


class FeatureType(str, Enum):
    PRICE = "price"
    VOLUME = "volume"
    ORDERBOOK = "orderbook"
    TREND = "trend"
    MOMENTUM = "momentum"
    VOLATILITY = "volatility"
    LIQUIDITY = "liquidity"
    MICROSTRUCTURE = "microstructure"
    SENTIMENT = "sentiment"
    CUSTOM = "custom"


class FeatureComputationMode(str, Enum):
    ONLINE = "online"
    BATCH = "batch"
    HYBRID = "hybrid"


@dataclass
class FeatureWindowConfig:
    """特征窗口配置"""
    window_size: int = 20
    window_type: str = "rolling"
    min_periods: int = 5


@dataclass
class FeatureNormalizationConfig:
    """特征归一化配置"""
    enabled: bool = True
    method: str = "zscore"
    clip_range: Optional[List[float]] = field(default_factory=lambda: [-3.0, 3.0])


@dataclass(frozen=True)
class FeatureConfig:
    """
    单个特征配置
    
    核心特性：
    - 不可变
    - 完整的参数验证
    - 支持归一化和窗口配置
    """
    feature_id: str
    feature_name: str
    feature_type: FeatureType
    
    version: str = "1.0.0"
    is_enabled: bool = True
    
    # 计算配置
    computation_mode: FeatureComputationMode = FeatureComputationMode.ONLINE
    update_frequency_ms: int = 1000
    
    # 窗口和归一化
    window_config: FeatureWindowConfig = field(default_factory=FeatureWindowConfig)
    normalization_config: FeatureNormalizationConfig = field(default_factory=FeatureNormalizationConfig)
    
    # 特征参数
    feature_params: Dict[str, Any] = field(default_factory=dict)
    
    # 元数据
    created_at: datetime = field(default_factory=datetime.utcnow)
    description: str = ""
    
    def __post_init__(self):
        assert self.feature_id, "feature_id cannot be empty"
        assert self.feature_name, "feature_name cannot be empty"
        assert self.window_config.window_size > 0, "window_size must be positive"
        assert self.window_config.min_periods <= self.window_config.window_size, "min_periods cannot exceed window_size"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature_id": self.feature_id,
            "feature_name": self.feature_name,
            "feature_type": self.feature_type.value,
            "version": self.version,
            "is_enabled": self.is_enabled,
            "computation_mode": self.computation_mode.value,
            "update_frequency_ms": self.update_frequency_ms,
            "window_config": {
                "window_size": self.window_config.window_size,
                "window_type": self.window_config.window_type,
                "min_periods": self.window_config.min_periods,
            },
            "normalization_config": {
                "enabled": self.normalization_config.enabled,
                "method": self.normalization_config.method,
                "clip_range": self.normalization_config.clip_range,
            },
            "feature_params": self.feature_params,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
        }


@dataclass(frozen=True)
class FeatureSetConfig:
    """特征集合配置"""
    feature_set_id: str
    feature_set_name: str
    
    features: List[FeatureConfig] = field(default_factory=list)
    required_features: Set[str] = field(default_factory=set)
    
    version: str = "1.0.0"
    created_at: datetime = field(default_factory=datetime.utcnow)
    description: str = ""
    
    @property
    def all_feature_ids(self) -> List[str]:
        return [f.feature_id for f in self.features]
    
    def get_feature(self, feature_id: str) -> Optional[FeatureConfig]:
        for feat in self.features:
            if feat.feature_id == feature_id:
                return feat
        return None
