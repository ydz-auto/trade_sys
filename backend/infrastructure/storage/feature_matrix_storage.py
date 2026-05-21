"""
Data Lake Feature Matrix Storage - 特征矩阵存储

目录结构：
data_lake/
  feature_matrix/
    historical/
      symbol=BTCUSDT/
        interval=60s/
          data.parquet
        interval=300s/
          data.parquet
    realtime/
      (in-memory, managed by runtime)
"""

from pathlib import Path
from typing import Optional

from infrastructure.logging import get_logger

logger = get_logger("storage.feature_matrix")

DATA_LAKE_ROOT = Path(r"e:\00_crypto\00_code\backend\data_lake")
FEATURE_MATRIX_ROOT = DATA_LAKE_ROOT / "feature_matrix"
HISTORICAL_ROOT = FEATURE_MATRIX_ROOT / "historical"
REALTIME_ROOT = FEATURE_MATRIX_ROOT / "realtime"


def ensure_storage_directories():
    """确保存储目录存在"""
    HISTORICAL_ROOT.mkdir(parents=True, exist_ok=True)
    REALTIME_ROOT.mkdir(parents=True, exist_ok=True)
    logger.info(f"Storage directories initialized at {FEATURE_MATRIX_ROOT}")


def get_historical_path(symbol: str, interval_ms: int) -> Path:
    """获取历史特征矩阵存储路径"""
    interval_str = f"{interval_ms // 1000}s"
    return HISTORICAL_ROOT / f"symbol={symbol}" / f"interval={interval_str}" / "data.parquet"


def has_historical_matrix(symbol: str, interval_ms: int) -> bool:
    """检查是否存在历史特征矩阵"""
    path = get_historical_path(symbol, interval_ms)
    return path.exists()


# 初始化存储目录
ensure_storage_directories()

