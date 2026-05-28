"""
Memory Optimizer - 内存优化器

提供 DataFrame 内存优化能力：
- float / int 类型降级
- 自动类型优化
- 列释放与垃圾回收
- 内存估算
- Parquet 批量读写

用法：
    from infrastructure.acceleration.memory_optimizer import MemoryOptimizer

    optimizer = MemoryOptimizer()

    df_optimized = optimizer.optimize_dtypes(df)
    memory_bytes = optimizer.estimate_dataframe_memory(df)
"""
import gc
import logging
from pathlib import Path
from typing import Iterator, List, Optional

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

logger = logging.getLogger(__name__)

_INT_CANDIDATES = [np.int8, np.int16, np.int32, np.int64]


class MemoryOptimizer:

    @staticmethod
    def downcast_float(df: pd.DataFrame, target: str = "float32") -> pd.DataFrame:
        df = df.copy()
        float_cols = df.select_dtypes(include=["float64"]).columns
        if len(float_cols) > 0:
            df[float_cols] = df[float_cols].astype(target)
            logger.debug(f"Downcasted {len(float_cols)} float64 columns to {target}")
        return df

    @staticmethod
    def downcast_int(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        int_cols = df.select_dtypes(include=["int64"]).columns
        for col in int_cols:
            col_min = df[col].min()
            col_max = df[col].max()
            for candidate in _INT_CANDIDATES:
                info = np.iinfo(candidate)
                if info.min <= col_min <= info.max and info.min <= col_max <= info.max:
                    df[col] = df[col].astype(candidate)
                    break
        logger.debug(f"Downcasted {len(int_cols)} int64 columns")
        return df

    @classmethod
    def optimize_dtypes(cls, df: pd.DataFrame) -> pd.DataFrame:
        df = cls.downcast_float(df)
        df = cls.downcast_int(df)
        return df

    @staticmethod
    def release_columns(df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
        existing = [c for c in columns if c in df.columns]
        if existing:
            df = df.drop(columns=existing)
            gc.collect()
            logger.debug(f"Released columns: {existing}")
        return df

    @staticmethod
    def estimate_dataframe_memory(df: pd.DataFrame) -> int:
        return int(df.memory_usage(deep=True).sum())

    @staticmethod
    def read_parquet_batch(
        path: Path,
        columns: Optional[List[str]] = None,
        row_groups: Optional[int] = None,
    ) -> Iterator[pd.DataFrame]:
        pf = pq.ParquetFile(path)
        total_groups = pf.metadata.num_row_groups
        limit = row_groups if row_groups is not None else total_groups
        for i in range(min(limit, total_groups)):
            table = pf.read_row_group(i, columns=columns)
            yield table.to_pandas()

    @staticmethod
    def write_parquet_batch(path: Path, dfs: Iterator[pd.DataFrame]) -> Path:
        collected = list(dfs)
        if not collected:
            logger.warning("No DataFrames to write")
            return path
        combined = pd.concat(collected, ignore_index=True)
        combined.to_parquet(path, engine="pyarrow", compression="zstd")
        logger.debug(f"Wrote parquet to {path}")
        return path
