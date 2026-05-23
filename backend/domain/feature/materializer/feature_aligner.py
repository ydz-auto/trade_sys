"""
Feature Aligner - 特征时间对齐器

核心功能：
- 多源特征时间对齐
- 前向填充/后向填充/插值
- 统一时间粒度对齐
"""

from typing import List, Optional, Dict, Any
import pandas as pd
import numpy as np
from datetime import datetime
from dataclasses import dataclass

from domain.logging import get_logger

logger = get_logger("feature.materializer.aligner")


@dataclass
class AlignedFeatureData:
    """对齐后的特征数据"""
    timestamps: List[int]
    features: Dict[str, List[float]]


class FeatureAligner:
    """特征时间对齐器"""
    
    def __init__(self, interval_ms: int = 60000):
        self.interval_ms = interval_ms
    
    def align_features(
        self,
        feature_dfs: Dict[str, pd.DataFrame],
        start_ts: Optional[int] = None,
        end_ts: Optional[int] = None,
        fill_method: str = "ffill"
    ) -> AlignedFeatureData:
        """
        对齐多个特征DataFrame
        
        Args:
            feature_dfs: {feature_name: df}，每个df必须有timestamp列
            start_ts: 开始时间戳(ms)，None则取最早
            end_ts: 结束时间戳(ms)，None则取最晚
            fill_method: 填充方法 "ffill" | "bfill" | "interpolate"
        """
        all_timestamps = set()
        
        # 收集所有时间戳
        for name, df in feature_dfs.items():
            if df is not None and not df.empty:
                if "timestamp" in df.columns:
                    all_timestamps.update(df["timestamp"].tolist())
                elif df.index.name == "timestamp":
                    all_timestamps.update(df.index.tolist())
        
        if not all_timestamps:
            return AlignedFeatureData(timestamps=[], features={})
        
        # 生成对齐后的时间序列
        min_ts = start_ts if start_ts is not None else min(all_timestamps)
        max_ts = end_ts if end_ts is not None else max(all_timestamps)
        
        aligned_timestamps = self._generate_aligned_timestamps(min_ts, max_ts)
        
        result_features: Dict[str, List[float]] = {}
        
        # 对齐每个特征
        for name, df in feature_dfs.items():
            if df is None or df.empty:
                continue
            
            aligned_values = self._align_single_feature(df, aligned_timestamps, fill_method)
            result_features[name] = aligned_values
        
        return AlignedFeatureData(
            timestamps=aligned_timestamps,
            features=result_features
        )
    
    def _generate_aligned_timestamps(self, min_ts: int, max_ts: int) -> List[int]:
        """生成对齐后的时间戳序列"""
        aligned = []
        current = min_ts - (min_ts % self.interval_ms)
        
        while current <= max_ts:
            aligned.append(current)
            current += self.interval_ms
        
        return aligned
    
    def _align_single_feature(
        self,
        df: pd.DataFrame,
        target_timestamps: List[int],
        fill_method: str
    ) -> List[float]:
        """对齐单个特征"""
        # 确保有timestamp列
        if "timestamp" not in df.columns and df.index.name != "timestamp":
            raise ValueError("DataFrame must have timestamp column or index")
        
        # 提取时间戳和所有数值列
        if "timestamp" in df.columns:
            df = df.set_index("timestamp")
        
        # 只保留数值列
        numeric_df = df.select_dtypes(include=[np.number])
        
        if numeric_df.empty:
            return [0.0] * len(target_timestamps)
        
        # 创建目标索引
        target_index = pd.Index(target_timestamps, name="timestamp")
        
        # 重新索引并填充
        aligned_df = numeric_df.reindex(target_index)
        
        if fill_method == "ffill":
            aligned_df = aligned_df.ffill()
        elif fill_method == "bfill":
            aligned_df = aligned_df.bfill()
        elif fill_method == "interpolate":
            aligned_df = aligned_df.interpolate()
        
        # 填充剩余NaN
        aligned_df = aligned_df.fillna(0.0)
        
        # 返回第一列（如果有多列，取第一列）
        return aligned_df.iloc[:, 0].tolist()

