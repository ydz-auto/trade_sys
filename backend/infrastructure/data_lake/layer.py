"""
Data Lake Layer System - 数据湖分层体系

设计原则：
1. 分层存储：raw → normalized → aggregated → feature → signal → replay
2. 生命周期管理：TTL、冷热分离
3. 查询优化：物化视图、分区策略
4. 数据血缘：追踪数据来源和转换

数据流向：
raw (原始数据)
    ↓ normalize
normalized (标准化数据)
    ↓ aggregate
aggregated (聚合数据: K线、特征)
    ↓ extract
feature (特征数据)
    ↓ analyze
signal (信号数据)
    ↓
replay (回放数据)
"""

from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta


class DataLayer(str, Enum):
    """数据层级"""
    RAW = "raw"
    NORMALIZED = "normalized"
    AGGREGATED = "aggregated"
    FEATURE = "feature"
    SIGNAL = "signal"
    REPLAY = "replay"
    
    @classmethod
    def ordered_layers(cls) -> List["DataLayer"]:
        """获取有序层级列表"""
        return [
            cls.RAW,
            cls.NORMALIZED,
            cls.AGGREGATED,
            cls.FEATURE,
            cls.SIGNAL,
            cls.REPLAY,
        ]
    
    def downstream(self) -> Optional["DataLayer"]:
        """获取下游层级"""
        layers = self.ordered_layers()
        idx = layers.index(self)
        if idx < len(layers) - 1:
            return layers[idx + 1]
        return None
    
    def upstream(self) -> Optional["DataLayer"]:
        """获取上游层级"""
        layers = self.ordered_layers()
        idx = layers.index(self)
        if idx > 0:
            return layers[idx - 1]
        return None


class DataCategory(str, Enum):
    """数据类别"""
    MARKET = "market"
    NEWS = "news"
    SOCIAL = "social"
    ONCHAIN = "onchain"
    MACRO = "macro"
    ETF = "etf"
    ORDER = "order"
    TRADE = "trade"
    POSITION = "position"


@dataclass
class LayerConfig:
    """层级配置"""
    layer: DataLayer
    ttl_days: int
    partition_by: str
    order_by: List[str]
    
    hot_storage_days: int = 7
    warm_storage_days: int = 30
    cold_storage_days: int = 90
    
    enable_materialized_view: bool = True
    compression: str = "LZ4"
    
    def get_ttl_sql(self) -> str:
        """生成TTL SQL"""
        return f"TTL toDateTime(timestamp) + INTERVAL {self.ttl_days} DAY"
    
    def get_partition_sql(self) -> str:
        """生成分区SQL"""
        return f"PARTITION BY {self.partition_by}"


@dataclass
class DataLineage:
    """数据血缘"""
    data_id: str
    layer: DataLayer
    category: DataCategory
    
    source_layer: Optional[DataLayer] = None
    source_ids: List[str] = field(default_factory=list)
    
    transform_fn: Optional[str] = None
    transform_params: Dict[str, Any] = field(default_factory=dict)
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "data_id": self.data_id,
            "layer": self.layer.value,
            "category": self.category.value,
            "source_layer": self.source_layer.value if self.source_layer else None,
            "source_ids": self.source_ids,
            "transform_fn": self.transform_fn,
            "transform_params": self.transform_params,
            "created_at": self.created_at.isoformat(),
        }


LAYER_CONFIGS: Dict[DataLayer, LayerConfig] = {
    DataLayer.RAW: LayerConfig(
        layer=DataLayer.RAW,
        ttl_days=30,
        partition_by="toYYYYMMDD(timestamp)",
        order_by=["source", "timestamp"],
        hot_storage_days=3,
        warm_storage_days=7,
        cold_storage_days=30,
        enable_materialized_view=False,
    ),
    DataLayer.NORMALIZED: LayerConfig(
        layer=DataLayer.NORMALIZED,
        ttl_days=60,
        partition_by="toYYYYMM(timestamp)",
        order_by=["category", "symbol", "timestamp"],
        hot_storage_days=7,
        warm_storage_days=30,
        cold_storage_days=60,
    ),
    DataLayer.AGGREGATED: LayerConfig(
        layer=DataLayer.AGGREGATED,
        ttl_days=180,
        partition_by="toYYYYMM(timestamp)",
        order_by=["symbol", "timeframe", "timestamp"],
        hot_storage_days=14,
        warm_storage_days=60,
        cold_storage_days=180,
    ),
    DataLayer.FEATURE: LayerConfig(
        layer=DataLayer.FEATURE,
        ttl_days=90,
        partition_by="toYYYYMM(timestamp)",
        order_by=["symbol", "timestamp"],
        hot_storage_days=7,
        warm_storage_days=30,
        cold_storage_days=90,
    ),
    DataLayer.SIGNAL: LayerConfig(
        layer=DataLayer.SIGNAL,
        ttl_days=30,
        partition_by="toYYYYMM(timestamp)",
        order_by=["symbol", "timestamp"],
        hot_storage_days=3,
        warm_storage_days=14,
        cold_storage_days=30,
    ),
    DataLayer.REPLAY: LayerConfig(
        layer=DataLayer.REPLAY,
        ttl_days=365,
        partition_by="toYYYYMM(timestamp)",
        order_by=["replay_id", "timestamp"],
        hot_storage_days=30,
        warm_storage_days=90,
        cold_storage_days=365,
        enable_materialized_view=False,
    ),
}


def get_layer_config(layer: DataLayer) -> LayerConfig:
    """获取层级配置"""
    return LAYER_CONFIGS[layer]
