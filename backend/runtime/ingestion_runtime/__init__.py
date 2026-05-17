"""
Ingestion Runtime - 数据采集 + 聚合运行时

合并 data_service + aggregation_service

职责：
1. 从多个数据源采集数据（新闻、行情等）
2. 聚合数据（K线、订单簿、成交）
3. 发布到 Kafka

用法:
    python -m runtime.ingestion_runtime
"""

from runtime.ingestion_runtime.runtime import IngestionRuntime, get_ingestion_runtime

__all__ = ["IngestionRuntime", "get_ingestion_runtime"]
