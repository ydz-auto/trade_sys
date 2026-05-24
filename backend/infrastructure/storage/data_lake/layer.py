"""
Data Lake Layer System - 数据湖分层体系

设计原则：
1. 分层存储：raw → normalized → aggregated → feature → signal → replay
2. 生命周期管理：TTL、冷热分离
3. 查询优化：物化视图、分区策略
4. 数据血缘：追踪数据来源和转换

本文件是数据湖层级配置的**唯一来源** (Single Source of Truth)。
所有 TTL、分区策略、排序键等配置均从此处读取，
schemas.py 等其他文件通过 get_layer_config() 动态生成 SQL。
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta


class DataLayer(str, Enum):
    RAW = "raw"
    NORMALIZED = "normalized"
    AGGREGATED = "aggregated"
    FEATURE = "feature"
    SIGNAL = "signal"
    REPLAY = "replay"

    @classmethod
    def ordered_layers(cls) -> List["DataLayer"]:
        return [
            cls.RAW,
            cls.NORMALIZED,
            cls.AGGREGATED,
            cls.FEATURE,
            cls.SIGNAL,
            cls.REPLAY,
        ]

    def downstream(self) -> Optional["DataLayer"]:
        layers = self.ordered_layers()
        idx = layers.index(self)
        if idx < len(layers) - 1:
            return layers[idx + 1]
        return None

    def upstream(self) -> Optional["DataLayer"]:
        layers = self.ordered_layers()
        idx = layers.index(self)
        if idx > 0:
            return layers[idx - 1]
        return None


class DataCategory(str, Enum):
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
        return f"TTL toDateTime(timestamp) + INTERVAL {self.ttl_days} DAY"

    def get_partition_sql(self) -> str:
        return f"PARTITION BY {self.partition_by}"


@dataclass
class DataLineage:
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
        ttl_days=90,
        partition_by="toYYYYMMDD(timestamp)",
        order_by=["source", "timestamp"],
        hot_storage_days=3,
        warm_storage_days=30,
        cold_storage_days=90,
        enable_materialized_view=False,
    ),
    DataLayer.NORMALIZED: LayerConfig(
        layer=DataLayer.NORMALIZED,
        ttl_days=180,
        partition_by="toYYYYMM(timestamp)",
        order_by=["category", "symbol", "timestamp"],
        hot_storage_days=7,
        warm_storage_days=60,
        cold_storage_days=180,
    ),
    DataLayer.AGGREGATED: LayerConfig(
        layer=DataLayer.AGGREGATED,
        ttl_days=365,
        partition_by="toYYYYMM(timestamp)",
        order_by=["symbol", "timeframe", "timestamp"],
        hot_storage_days=14,
        warm_storage_days=90,
        cold_storage_days=365,
    ),
    DataLayer.FEATURE: LayerConfig(
        layer=DataLayer.FEATURE,
        ttl_days=180,
        partition_by="toYYYYMM(timestamp)",
        order_by=["symbol", "timestamp"],
        hot_storage_days=7,
        warm_storage_days=60,
        cold_storage_days=180,
    ),
    DataLayer.SIGNAL: LayerConfig(
        layer=DataLayer.SIGNAL,
        ttl_days=365,
        partition_by="toYYYYMM(timestamp)",
        order_by=["symbol", "timestamp"],
        hot_storage_days=7,
        warm_storage_days=90,
        cold_storage_days=365,
    ),
    DataLayer.REPLAY: LayerConfig(
        layer=DataLayer.REPLAY,
        ttl_days=730,
        partition_by="toYYYYMM(timestamp)",
        order_by=["replay_id", "timestamp"],
        hot_storage_days=30,
        warm_storage_days=180,
        cold_storage_days=730,
        enable_materialized_view=False,
    ),
}


def get_layer_config(layer: DataLayer) -> LayerConfig:
    return LAYER_CONFIGS[layer]
