"""
Feature Matrix Module (Converged Version) - 统一特征矩阵 (收敛版)

核心功能：
- 基于6大Feature Group的统一特征矩阵
- 支持历史和实时模式
- 与materializer层集成
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
import pandas as pd

from infrastructure.logging import get_logger
from domain.feature.materializer import (
    UnifiedFeatureMatrix,
    HistoricalFeatureMaterializer,
    RealtimeFeatureMaterializer,
    get_schema_registry
)

logger = get_logger("feature.feature_matrix")

DATA_LAKE_ROOT = Path(r"e:\00_crypto\00_code\backend\data_lake")


def get_historical_feature_matrix(
    symbol: str,
    interval_ms: int = 60000,
    limit: Optional[int] = None,
    start_ts: Optional[int] = None,
    end_ts: Optional[int] = None,
    force: bool = False
) -> UnifiedFeatureMatrix:
    """获取历史特征矩阵（收敛版）"""
    materializer = HistoricalFeatureMaterializer(DATA_LAKE_ROOT)
    
    matrix = materializer.materialize_symbol(
        symbol=symbol,
        interval_ms=interval_ms,
        start_ts=start_ts,
        end_ts=end_ts,
        force=force
    )
    
    if limit is not None and len(matrix.timestamps) > limit:
        matrix = UnifiedFeatureMatrix(
            symbol=matrix.symbol,
            interval_ms=matrix.interval_ms,
            timestamps=matrix.timestamps[-limit:],
            feature_vector={
                name: values[-limit:]
                for name, values in matrix.feature_vector.items()
            },
            metadata=matrix.metadata
        )
    
    return matrix


def save_unified_matrix(matrix: UnifiedFeatureMatrix, path: Path):
    """保存统一特征矩阵"""
    path.parent.mkdir(parents=True, exist_ok=True)
    df = matrix.to_dataframe()
    df.to_parquet(path, compression="zstd")


def load_unified_matrix(path: Path) -> UnifiedFeatureMatrix:
    """加载统一特征矩阵"""
    df = pd.read_parquet(path)
    timestamps = df.index.tolist()
    
    feature_vector = {}
    for col in df.columns:
        if col != "datetime":
            feature_vector[col] = df[col].tolist()
    
    symbol = str(path.parent.parent.name).replace("symbol=", "")
    interval_str = str(path.parent.name).replace("interval=", "")
    interval_ms = int(interval_str.replace("s", "")) * 1000 if "s" in interval_str else 60000
    
    return UnifiedFeatureMatrix(
        symbol=symbol,
        interval_ms=interval_ms,
        timestamps=timestamps,
        feature_vector=feature_vector,
        metadata={"loaded_from": str(path)}
    )


def get_available_features() -> List[Dict[str, Any]]:
    """获取可用特征列表（收敛版6大组）"""
    registry = get_schema_registry()
    return [
        {
            "name": schema.name,
            "category": schema.category.value,
            "description": schema.description,
            "is_required": schema.is_required
        }
        for schema in registry.get_all_schemas()
    ]

