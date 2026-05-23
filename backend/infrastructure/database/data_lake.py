"""
Data Lake 分层存储管理
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any

from infrastructure.data_lake.layer import DataLayer, LAYER_CONFIGS
from infrastructure.database.clickhouse import ClickHouseManager
from infrastructure.database.schemas.data_lake import (
    DATA_LAKE_TABLE_SCHEMAS,
    DATA_LAKE_MATERIALIZED_VIEWS,
    DATA_LAKE_SCHEMAS,
)
from infrastructure.logging import get_logger

logger = get_logger("infrastructure.database.data_lake")


DataLakeLayer = DataLayer


@dataclass
class DataLakeConfig:
    raw_ttl_days: int = LAYER_CONFIGS[DataLayer.RAW].ttl_days
    normalized_ttl_days: int = LAYER_CONFIGS[DataLayer.NORMALIZED].ttl_days
    aggregated_ttl_days: int = LAYER_CONFIGS[DataLayer.AGGREGATED].ttl_days
    feature_ttl_days: int = LAYER_CONFIGS[DataLayer.FEATURE].ttl_days
    signal_ttl_days: int = LAYER_CONFIGS[DataLayer.SIGNAL].ttl_days
    replay_ttl_days: int = LAYER_CONFIGS[DataLayer.REPLAY].ttl_days
    hot_storage_hours: int = 24
    warm_storage_days: int = 30


@dataclass
class DataLakeTable:
    name: str
    layer: DataLakeLayer
    engine: str
    partition_by: str
    order_by: str
    ttl_expression: str
    schema_sql: str


_LAYER_TABLE_MAPPING: Dict[DataLakeLayer, List[str]] = {
    DataLakeLayer.RAW: [
        "lake_raw_trades",
        "lake_raw_klines",
        "lake_raw_news",
        "lake_raw_orderbook",
    ],
    DataLakeLayer.NORMALIZED: [
        "lake_normalized_trades",
        "lake_normalized_klines",
    ],
    DataLakeLayer.AGGREGATED: [
        "lake_aggregated_klines",
        "lake_aggregated_vwap",
        "lake_aggregated_footprint",
    ],
    DataLakeLayer.FEATURE: [
        "lake_feature_technical",
        "lake_feature_factor",
    ],
    DataLakeLayer.SIGNAL: [
        "lake_signal_trading",
        "lake_signal_fusion",
    ],
    DataLakeLayer.REPLAY: [
        "lake_replay_events",
        "lake_replay_snapshots",
    ],
}

_LAYER_TTL_MAPPING: Dict[DataLakeLayer, str] = {
    DataLakeLayer.RAW: "raw_ttl_days",
    DataLakeLayer.NORMALIZED: "normalized_ttl_days",
    DataLakeLayer.AGGREGATED: "aggregated_ttl_days",
    DataLakeLayer.FEATURE: "feature_ttl_days",
    DataLakeLayer.SIGNAL: "signal_ttl_days",
    DataLakeLayer.REPLAY: "replay_ttl_days",
}


class DataLakeManager:
    """数据湖管理器

    职责：
    1. 管理数据分层存储
    2. 自动路由写入到正确的层
    3. 管理TTL和生命周期
    4. 提供跨层查询能力
    5. 管理物化视图
    """

    def __init__(
        self,
        config: Optional[DataLakeConfig] = None,
        clickhouse_manager: Optional[ClickHouseManager] = None,
    ):
        self.config = config or DataLakeConfig()
        self._ch_manager = clickhouse_manager
        self._initialized = False

    @property
    def ch_manager(self) -> ClickHouseManager:
        if self._ch_manager is None:
            self._ch_manager = ClickHouseManager()
        return self._ch_manager

    async def initialize(self) -> None:
        """初始化所有层的表和物化视图"""
        for table_name, schema_sql in DATA_LAKE_TABLE_SCHEMAS.items():
            try:
                await self.ch_manager.execute(schema_sql)
                logger.info(f"Initialized data lake table: {table_name}")
            except Exception as e:
                logger.error(f"Error initializing table {table_name}: {e}")
                raise

        for view_name, view_sql in DATA_LAKE_MATERIALIZED_VIEWS.items():
            try:
                await self.ch_manager.execute(view_sql)
                logger.info(f"Initialized materialized view: {view_name}")
            except Exception as e:
                logger.error(f"Error initializing materialized view {view_name}: {e}")
                raise

        self._initialized = True
        logger.info("Data lake initialized successfully")

    async def write(self, layer: DataLakeLayer, table: str, data: List[Dict]) -> None:
        """写入数据到指定层"""
        if not data:
            return

        layer_tables = _LAYER_TABLE_MAPPING.get(layer, [])
        if table not in layer_tables:
            raise ValueError(
                f"Table '{table}' does not belong to layer '{layer.value}'. "
                f"Expected tables: {layer_tables}"
            )

        try:
            await self.ch_manager.insert(table, data)
            logger.debug(
                f"Wrote {len(data)} rows to {layer.value}.{table}"
            )
        except Exception as e:
            logger.error(f"Error writing to {layer.value}.{table}: {e}")
            raise

    async def read(
        self,
        layer: DataLakeLayer,
        table: str,
        query: str,
        params: Optional[Dict] = None,
    ) -> List[Dict]:
        """从指定层读取数据"""
        layer_tables = _LAYER_TABLE_MAPPING.get(layer, [])
        if table not in layer_tables:
            raise ValueError(
                f"Table '{table}' does not belong to layer '{layer.value}'. "
                f"Expected tables: {layer_tables}"
            )

        try:
            result = await self.ch_manager.fetch(query)
            return result
        except Exception as e:
            logger.error(f"Error reading from {layer.value}.{table}: {e}")
            raise

    async def migrate_layer(
        self,
        source_layer: DataLakeLayer,
        target_layer: DataLakeLayer,
        table: str,
        criteria: Dict,
    ) -> int:
        """数据在层间迁移"""
        source_tables = _LAYER_TABLE_MAPPING.get(source_layer, [])
        target_tables = _LAYER_TABLE_MAPPING.get(target_layer, [])

        if table not in source_tables:
            raise ValueError(
                f"Table '{table}' does not belong to source layer '{source_layer.value}'"
            )

        target_table = table.replace(f"lake_{source_layer.value}_", f"lake_{target_layer.value}_")
        if target_table not in target_tables:
            raise ValueError(
                f"Target table '{target_table}' does not belong to target layer '{target_layer.value}'"
            )

        where_clauses = []
        for key, value in criteria.items():
            if isinstance(value, str):
                where_clauses.append(f"{key} = '{value}'")
            elif isinstance(value, (int, float)):
                where_clauses.append(f"{key} = {value}")
            else:
                where_clauses.append(f"{key} = '{value}'")

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        insert_query = (
            f"INSERT INTO {target_table} "
            f"SELECT * FROM {table} WHERE {where_sql}"
        )

        try:
            count_query = f"SELECT count() AS cnt FROM {table} WHERE {where_sql}"
            count_result = await self.ch_manager.fetch(count_query)
            migrated_count = count_result[0].get("cnt", 0) if count_result else 0

            await self.ch_manager.execute(insert_query)
            logger.info(
                f"Migrated {migrated_count} rows from {source_layer.value}.{table} "
                f"to {target_layer.value}.{target_table}"
            )
            return migrated_count
        except Exception as e:
            logger.error(f"Error migrating data: {e}")
            raise

    async def create_materialized_view(
        self,
        view_name: str,
        source_table: str,
        target_table: str,
        transform_sql: str,
    ) -> None:
        """创建物化视图"""
        create_sql = (
            f"CREATE MATERIALIZED VIEW IF NOT EXISTS {view_name} "
            f"TO {target_table} "
            f"AS {transform_sql}"
        )

        try:
            await self.ch_manager.execute(create_sql)
            logger.info(f"Created materialized view: {view_name}")
        except Exception as e:
            logger.error(f"Error creating materialized view {view_name}: {e}")
            raise

    async def get_layer_stats(self, layer: DataLakeLayer) -> Dict[str, Any]:
        """获取层统计信息"""
        tables = _LAYER_TABLE_MAPPING.get(layer, [])
        stats: Dict[str, Any] = {
            "layer": layer.value,
            "tables": {},
            "total_rows": 0,
            "total_bytes": 0,
        }

        for table_name in tables:
            try:
                table_stats = await self.get_table_stats(table_name)
                stats["tables"][table_name] = table_stats
                stats["total_rows"] += table_stats.get("rows", 0)
                stats["total_bytes"] += table_stats.get("bytes", 0)
            except Exception as e:
                logger.error(f"Error getting stats for {table_name}: {e}")
                stats["tables"][table_name] = {"error": str(e)}

        ttl_field = _LAYER_TTL_MAPPING.get(layer)
        if ttl_field:
            stats["ttl_days"] = getattr(self.config, ttl_field)

        return stats

    async def get_table_stats(self, table_name: str) -> Dict[str, Any]:
        """获取表统计信息"""
        try:
            query = (
                f"SELECT "
                f"  name, "
                f"  total_rows, "
                f"  total_bytes, "
                f"  parts, "
                f"  rows, "
                f"  bytes_on_disk "
                f"FROM system.tables "
                f"WHERE name = '{table_name}'"
            )
            result = await self.ch_manager.fetch(query)

            if result:
                row = result[0]
                return {
                    "name": row.get("name", table_name),
                    "rows": row.get("total_rows", 0) or row.get("rows", 0),
                    "bytes": row.get("total_bytes", 0) or row.get("bytes_on_disk", 0),
                    "parts": row.get("parts", 0),
                }

            return {
                "name": table_name,
                "rows": 0,
                "bytes": 0,
                "parts": 0,
            }
        except Exception as e:
            logger.error(f"Error getting table stats for {table_name}: {e}")
            return {
                "name": table_name,
                "error": str(e),
            }

    async def optimize_table(self, table_name: str) -> None:
        """优化表（触发merge）"""
        try:
            await self.ch_manager.execute(f"OPTIMIZE TABLE {table_name} FINAL")
            logger.info(f"Optimized table: {table_name}")
        except Exception as e:
            logger.error(f"Error optimizing table {table_name}: {e}")
            raise

    async def cleanup_expired(self) -> Dict[str, int]:
        """清理过期数据"""
        cleaned: Dict[str, int] = {}
        all_tables = []

        for tables in _LAYER_TABLE_MAPPING.values():
            all_tables.extend(tables)

        for table_name in all_tables:
            try:
                before_query = f"SELECT count() AS cnt FROM {table_name} WHERE ingest_time < now() - INTERVAL 1 DAY"
                before_result = await self.ch_manager.fetch(before_query)
                expired_count = before_result[0].get("cnt", 0) if before_result else 0

                if expired_count > 0:
                    await self.optimize_table(table_name)
                    cleaned[table_name] = expired_count
                    logger.info(f"Cleaned up {expired_count} expired rows from {table_name}")
                else:
                    cleaned[table_name] = 0
            except Exception as e:
                logger.error(f"Error cleaning up {table_name}: {e}")
                cleaned[table_name] = -1

        return cleaned

    async def health_check(self) -> Dict[str, Any]:
        """数据湖健康检查"""
        health: Dict[str, Any] = {
            "initialized": self._initialized,
            "layers": {},
            "overall_healthy": True,
        }

        for layer in DataLakeLayer:
            try:
                stats = await self.get_layer_stats(layer)
                layer_healthy = True
                for table_name, table_stats in stats.get("tables", {}).items():
                    if "error" in table_stats:
                        layer_healthy = False
                        break

                health["layers"][layer.value] = {
                    "healthy": layer_healthy,
                    "table_count": len(stats.get("tables", {})),
                    "total_rows": stats.get("total_rows", 0),
                    "total_bytes": stats.get("total_bytes", 0),
                }

                if not layer_healthy:
                    health["overall_healthy"] = False
            except Exception as e:
                health["layers"][layer.value] = {
                    "healthy": False,
                    "error": str(e),
                }
                health["overall_healthy"] = False

        try:
            ch_healthy = await self.ch_manager.health_check()
            health["clickhouse_healthy"] = ch_healthy
            if not ch_healthy:
                health["overall_healthy"] = False
        except Exception as e:
            health["clickhouse_healthy"] = False
            health["clickhouse_error"] = str(e)
            health["overall_healthy"] = False

        return health


_data_lake_manager: Optional[DataLakeManager] = None


def get_data_lake_manager(
    config: Optional[DataLakeConfig] = None,
    clickhouse_manager: Optional[ClickHouseManager] = None,
) -> DataLakeManager:
    global _data_lake_manager
    if _data_lake_manager is None:
        _data_lake_manager = DataLakeManager(config, clickhouse_manager)
    return _data_lake_manager


async def init_data_lake(
    config: Optional[DataLakeConfig] = None,
    clickhouse_manager: Optional[ClickHouseManager] = None,
) -> DataLakeManager:
    manager = get_data_lake_manager(config, clickhouse_manager)
    await manager.initialize()
    return manager


async def close_data_lake() -> None:
    global _data_lake_manager
    _data_lake_manager = None
