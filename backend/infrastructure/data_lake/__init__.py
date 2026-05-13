"""
Data Lake Module - 数据湖模块

提供分层数据存储和管理能力

层级：
- raw: 原始数据
- normalized: 标准化数据
- aggregated: 聚合数据
- feature: 特征数据
- signal: 信号数据
- replay: 回放数据
"""

from .layer import (
    DataLayer,
    DataCategory,
    DataLineage,
    LayerConfig,
    get_layer_config,
    LAYER_CONFIGS,
)
from .schemas import (
    DATA_LAKE_SCHEMAS,
    DATA_LAKE_VIEWS,
    get_all_schemas,
    get_all_materialized_views,
)
from .manager import (
    DataLakeManager,
    WriteRequest,
    QueryRequest,
    LayerStats,
    get_data_lake_manager,
)

__all__ = [
    "DataLayer",
    "DataCategory",
    "DataLineage",
    "LayerConfig",
    "get_layer_config",
    "LAYER_CONFIGS",
    "DATA_LAKE_SCHEMAS",
    "DATA_LAKE_VIEWS",
    "get_all_schemas",
    "get_all_materialized_views",
    "DataLakeManager",
    "WriteRequest",
    "QueryRequest",
    "LayerStats",
    "get_data_lake_manager",
]
