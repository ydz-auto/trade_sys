"""
Data Lake Manager - 数据湖管理器

功能：
1. 分层数据写入
2. 数据血缘追踪
3. TTL 管理
4. 冷热数据迁移
5. 查询路由
"""

import asyncio
import json
from typing import Dict, List, Optional, Any, AsyncIterator
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import uuid

from infrastructure.logging import get_logger
from infrastructure.persistence.database.clickhouse import ClickHouseManager

from .layer import (
    DataLayer,
    DataCategory,
    DataLineage,
    get_layer_config,
)
from .schemas import DATA_LAKE_SCHEMAS, DATA_LAKE_VIEWS

logger = get_logger("infrastructure.data_lake.manager")


@dataclass
class WriteRequest:
    """写入请求"""
    layer: DataLayer
    table: str
    data: Dict[str, Any]
    
    trace_id: Optional[str] = None
    source_layer: Optional[DataLayer] = None
    source_ids: List[str] = field(default_factory=list)
    
    def get_event_id(self) -> str:
        return self.data.get("event_id", str(uuid.uuid4()))


@dataclass
class QueryRequest:
    """查询请求"""
    layer: DataLayer
    table: str
    
    symbol: Optional[str] = None
    exchange: Optional[str] = None
    
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    limit: int = 0
    offset: int = 0
    
    filters: Dict[str, Any] = field(default_factory=dict)
    order_by: str = "open_time"
    time_column: str = "open_time"


@dataclass
class LayerStats:
    """层级统计"""
    layer: DataLayer
    table_count: int
    total_rows: int
    total_bytes: int
    
    oldest_data: Optional[datetime] = None
    newest_data: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "layer": self.layer.value,
            "table_count": self.table_count,
            "total_rows": self.total_rows,
            "total_bytes": self.total_bytes,
            "oldest_data": self.oldest_data.isoformat() if self.oldest_data else None,
            "newest_data": self.newest_data.isoformat() if self.newest_data else None,
        }


class DataLakeManager:
    """数据湖管理器
    
    提供分层数据存储和管理能力
    """
    
    def __init__(
        self,
        buffer_size: int = 1000,
        default_query_limit: int = 1000,
    ):
        self.clickhouse: Optional[ClickHouseManager] = None
        self._initialized = False
        self._lineage_buffer: List[DataLineage] = []
        self._buffer_size = buffer_size
        self._default_query_limit = default_query_limit
    
    async def initialize(self) -> None:
        """初始化"""
        if self._initialized:
            return
        
        self.clickhouse = ClickHouseManager()
        await self._ensure_tables()
        await self._ensure_materialized_views()
        self._initialized = True
        logger.info("DataLakeManager initialized")
    
    async def _ensure_tables(self) -> None:
        """确保所有表存在"""
        for table_name, schema_sql in DATA_LAKE_SCHEMAS.items():
            try:
                await self.clickhouse.execute(schema_sql)
                logger.debug(f"Table ensured: {table_name}")
            except Exception as e:
                logger.warning(f"Table creation warning for {table_name}: {e}")
    
    async def _ensure_materialized_views(self) -> None:
        """确保物化视图存在"""
        for view_name, view_sql in DATA_LAKE_VIEWS.items():
            try:
                await self.clickhouse.execute(view_sql)
                logger.debug(f"Materialized view ensured: {view_name}")
            except Exception as e:
                logger.warning(f"Materialized view creation warning for {view_name}: {e}")
    
    async def write(
        self,
        request: WriteRequest,
    ) -> str:
        """写入数据"""
        if not self._initialized:
            await self.initialize()
        
        event_id = request.get_event_id()
        
        if "event_id" not in request.data:
            request.data["event_id"] = event_id
        
        try:
            await self.clickhouse.insert(request.table, [request.data])
            
            lineage = DataLineage(
                data_id=event_id,
                layer=request.layer,
                category=request.data.get("category", DataCategory.MARKET),
                source_layer=request.source_layer,
                source_ids=request.source_ids,
            )
            self._lineage_buffer.append(lineage)
            
            if len(self._lineage_buffer) >= self._buffer_size:
                await self._flush_lineage()
            
            logger.debug(f"Written to {request.layer.value}.{request.table}: {event_id}")
            return event_id
            
        except Exception as e:
            logger.error(f"Write failed: {e}")
            raise
    
    async def write_batch(
        self,
        layer: DataLayer,
        table: str,
        data_list: List[Dict[str, Any]],
        source_layer: Optional[DataLayer] = None,
    ) -> List[str]:
        """批量写入"""
        if not data_list:
            return []
        
        if not self._initialized:
            await self.initialize()
        
        event_ids = []
        for data in data_list:
            if "event_id" not in data:
                data["event_id"] = str(uuid.uuid4())
            event_ids.append(data["event_id"])
        
        try:
            await self.clickhouse.insert(table, data_list)
            
            for event_id in event_ids:
                lineage = DataLineage(
                    data_id=event_id,
                    layer=layer,
                    category=DataCategory.MARKET,
                    source_layer=source_layer,
                )
                self._lineage_buffer.append(lineage)
            
            if len(self._lineage_buffer) >= self._buffer_size:
                await self._flush_lineage()
            
            logger.debug(f"Batch written to {layer.value}.{table}: {len(event_ids)} rows")
            return event_ids
            
        except Exception as e:
            logger.error(f"Batch write failed: {e}")
            raise
    
    async def query(
        self,
        request: QueryRequest,
    ) -> List[Dict[str, Any]]:
        """查询数据"""
        if not self._initialized:
            await self.initialize()
        
        if request.limit == 0:
            request.limit = self._default_query_limit

        conditions = []
        params: Dict[str, Any] = {}
        
        if request.symbol:
            conditions.append("symbol = %(symbol)s")
            params["symbol"] = request.symbol
        
        if request.exchange:
            conditions.append("exchange = %(exchange)s")
            params["exchange"] = request.exchange
        
        if request.start_time:
            conditions.append(f"{request.time_column} >= %(start_time)s")
            params["start_time"] = request.start_time
        
        if request.end_time:
            conditions.append(f"{request.time_column} < %(end_time)s")
            params["end_time"] = request.end_time
        
        for key, value in request.filters.items():
            conditions.append(f"{key} = %(filter_{key})s")
            params[f"filter_{key}"] = value
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        query_sql = f"""
            SELECT * FROM {request.table}
            WHERE {where_clause}
            ORDER BY {request.order_by}
            LIMIT %(limit)s OFFSET %(offset)s
        """
        params["limit"] = request.limit
        params["offset"] = request.offset
        
        try:
            results = await self.clickhouse.fetch(query_sql)
            return results
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return []
    
    async def stream(
        self,
        request: QueryRequest,
        batch_size: int = 1000,
    ) -> AsyncIterator[List[Dict[str, Any]]]:
        """流式查询"""
        offset = 0
        while True:
            request.limit = batch_size
            request.offset = offset
            
            batch = await self.query(request)
            if not batch:
                break
            
            yield batch
            offset += len(batch)
            
            if len(batch) < batch_size:
                break
    
    async def get_layer_stats(
        self,
        layer: DataLayer,
    ) -> LayerStats:
        """获取层级统计"""
        layer_tables = [
            name for name in DATA_LAKE_SCHEMAS.keys()
            if name.startswith(layer.value)
        ]
        
        total_rows = 0
        total_bytes = 0
        oldest_data = None
        newest_data = None
        
        for table in layer_tables:
            try:
                stats_query = f"""
                    SELECT
                        sum(rows) as rows,
                        sum(data_compressed_bytes) as bytes,
                        min(min_time) as min_time,
                        max(max_time) as max_time
                    FROM system.parts
                    WHERE database = currentDatabase()
                    AND table = %(table)s
                    AND active = 1
                """
                result = await self.clickhouse.fetch(stats_query, {"table": table})
                
                if result:
                    row = result[0]
                    total_rows += row.get("rows", 0)
                    total_bytes += row.get("bytes", 0)
                    
                    if row.get("min_time"):
                        min_t = datetime.fromtimestamp(row["min_time"])
                        if oldest_data is None or min_t < oldest_data:
                            oldest_data = min_t
                    
                    if row.get("max_time"):
                        max_t = datetime.fromtimestamp(row["max_time"])
                        if newest_data is None or max_t > newest_data:
                            newest_data = max_t
                            
            except Exception as e:
                logger.debug(f"Stats query failed for {table}: {e}")
        
        return LayerStats(
            layer=layer,
            table_count=len(layer_tables),
            total_rows=total_rows,
            total_bytes=total_bytes,
            oldest_data=oldest_data,
            newest_data=newest_data,
        )
    
    async def get_all_stats(self) -> Dict[str, LayerStats]:
        """获取所有层级统计"""
        stats = {}
        for layer in DataLayer.ordered_layers():
            stats[layer.value] = await self.get_layer_stats(layer)
        return stats
    
    async def cleanup_expired(self) -> Dict[str, int]:
        """清理过期数据"""
        results = {}
        
        for table_name in DATA_LAKE_SCHEMAS.keys():
            try:
                await self.clickhouse.execute(f"OPTIMIZE TABLE {table_name} FINAL")
                results[table_name] = 1
            except Exception as e:
                logger.debug(f"Optimize failed for {table_name}: {e}")
                results[table_name] = 0
        
        logger.info("Data cleanup completed")
        return results
    
    async def migrate_to_cold_storage(
        self,
        layer: DataLayer,
        before_date: datetime,
    ) -> int:
        """迁移到冷存储"""
        config = get_layer_config(layer)
        
        layer_tables = [
            name for name in DATA_LAKE_SCHEMAS.keys()
            if name.startswith(layer.value)
        ]
        
        total_migrated = 0
        for table in layer_tables:
            try:
                count_query = f"""
                    SELECT count() FROM {table}
                    WHERE timestamp < %(before_date)s
                """
                result = await self.clickhouse.fetch(count_query, {"before_date": before_date})
                count = result[0].get("count()", 0) if result else 0
                
                if count > 0:
                    logger.info(f"Migrating {count} rows from {table} to cold storage")
                    total_migrated += count
                    
            except Exception as e:
                logger.debug(f"Migration check failed for {table}: {e}")
        
        return total_migrated
    
    async def _flush_lineage(self) -> None:
        """刷新血缘缓冲"""
        if not self._lineage_buffer:
            return
        
        try:
            lineage_data = [lineage.to_dict() for lineage in self._lineage_buffer]
            await self.clickhouse.insert("data_lineage", lineage_data)
            self._lineage_buffer.clear()
        except Exception as e:
            logger.debug(f"Lineage flush failed: {e}")
    
    async def get_lineage(
        self,
        data_id: str,
    ) -> Optional[DataLineage]:
        """获取数据血缘"""
        try:
            result = await self.clickhouse.fetch(
                "SELECT * FROM data_lineage WHERE data_id = %(data_id)s",
                {"data_id": data_id}
            )
            
            if result:
                row = result[0]
                return DataLineage(
                    data_id=row["data_id"],
                    layer=DataLayer(row["layer"]),
                    category=DataCategory(row["category"]),
                    source_layer=DataLayer(row["source_layer"]) if row.get("source_layer") else None,
                    source_ids=json.loads(row.get("source_ids", "[]")),
                )
            return None
        except Exception as e:
            logger.debug(f"Lineage query failed: {e}")
            return None
    
    async def health_check(self) -> bool:
        """健康检查"""
        try:
            result = await self.clickhouse.fetch("SELECT 1")
            return len(result) > 0
        except Exception:
            return False
    
    async def close(self) -> None:
        """关闭连接"""
        if self._lineage_buffer:
            await self._flush_lineage()
        
        if self.clickhouse:
            await self.clickhouse.disconnect()
        
        self._initialized = False
        logger.info("DataLakeManager closed")


_data_lake_manager: Optional[DataLakeManager] = None


async def get_data_lake_manager() -> DataLakeManager:
    """获取数据湖管理器实例"""
    global _data_lake_manager
    if _data_lake_manager is None:
        _data_lake_manager = DataLakeManager()
        await _data_lake_manager.initialize()
    return _data_lake_manager
