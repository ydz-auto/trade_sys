"""
Infrastructure Storage Module - 基础设施存储模块
"""

from infrastructure.storage.feature_matrix_storage import (
    DATA_LAKE_ROOT,
    FEATURE_MATRIX_ROOT,
    HISTORICAL_ROOT,
    REALTIME_ROOT,
    ensure_storage_directories,
    get_historical_path,
    has_historical_matrix,
)

from infrastructure.storage.point_in_time_store import (
    PointInTimeFeatureStore,
    PointInTimeFeatureRecord,
    PointInTimeSnapshot,
    FeatureSourceType,
    get_point_in_time_store,
    clear_all_stores,
)

from infrastructure.storage.immutable_snapshot import (
    ImmutableFeatureSnapshot,
    ImmutableSnapshotStore,
    get_immutable_snapshot_store,
    create_immutable_snapshot,
)

__all__ = [
    "DATA_LAKE_ROOT",
    "FEATURE_MATRIX_ROOT",
    "HISTORICAL_ROOT",
    "REALTIME_ROOT",
    "ensure_storage_directories",
    "get_historical_path",
    "has_historical_matrix",
    "PointInTimeFeatureStore",
    "PointInTimeFeatureRecord",
    "PointInTimeSnapshot",
    "FeatureSourceType",
    "get_point_in_time_store",
    "clear_all_stores",
    "ImmutableFeatureSnapshot",
    "ImmutableSnapshotStore",
    "get_immutable_snapshot_store",
    "create_immutable_snapshot",
]
