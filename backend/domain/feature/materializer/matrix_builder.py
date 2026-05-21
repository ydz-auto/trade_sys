"""
Matrix Builder - 统一特征矩阵构建器

核心功能：
- 基于6大Feature Group构建timestamp × feature_vector矩阵
- 标准化特征值
- 缺失值处理
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import pandas as pd
import numpy as np

from infrastructure.logging import get_logger
from domain.feature.materializer.schema_registry import get_schema_registry, FeatureCategory

logger = get_logger("feature.materializer.matrix_builder")


@dataclass
class UnifiedFeatureMatrix:
    """统一特征矩阵 (收敛版)
    包含时间纪律信息，防止数据泄漏
    """
    symbol: str
    interval_ms: int
    timestamps: List[int]
    feature_vector: Dict[str, List[float]]  # {feature_name: [values]}
    metadata: Dict[str, Any]
    
    # 时间纪律字段
    feature_timestamps: Optional[Dict[str, List[int]]] = None  # 每个特征的计算时间戳
    available_ats: Optional[Dict[str, List[int]]] = None        # 每个特征的可用时间戳
    
    @property
    def shape(self) -> tuple:
        n_timestamps = len(self.timestamps)
        n_features = len(self.feature_vector)
        return (n_timestamps, n_features)
    
    def to_dataframe(self) -> pd.DataFrame:
        df = pd.DataFrame(self.feature_vector)
        df["timestamp"] = self.timestamps
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df.set_index("timestamp")
        return df
    
    def get_available_features_at(
        self,
        replay_clock: int,
        schema_registry: Any = None
    ) -> Dict[str, float]:
        """
        获取在指定回播时间可用的特征
        只返回在该时间点可用的特征，防止数据泄漏
        
        Args:
            replay_clock: 回播时间戳
            schema_registry: 特征Schema注册中心
            
        Returns:
            Dict[str, float]: 可用的特征值
        """
        if schema_registry is None:
            from domain.feature.materializer.schema_registry import get_schema_registry
            schema_registry = get_schema_registry()
        
        # 找到最接近且 <= replay_clock的时间索引
        idx = None
        for i, ts in enumerate(self.timestamps):
            if ts <= replay_clock:
                idx = i
            else:
                break
        
        if idx is None:
            return {}
        
        available_features = {}
        
        for feature_name, values in self.feature_vector.items():
            if idx >= len(values):
                continue
            
            # 检查特征是否可用
            schema = schema_registry.get_schema(feature_name)
            
            if self.available_ats and feature_name in self.available_ats:
                available_at = self.available_ats[feature_name][idx]
                if replay_clock < available_at:
                    continue  # 特征尚未可用
            
            elif schema and schema.available_after_periods > 0:
                # 根据schema计算可用时间
                feature_ts = self.timestamps[idx]
                available_at = feature_ts + (schema.available_after_periods * self.interval_ms)
                if replay_clock < available_at:
                    continue
            
            available_features[feature_name] = values[idx]
        
        return available_features
    
    def get_vector_at(self, timestamp: int) -> Optional[Dict[str, float]]:
        try:
            idx = self.timestamps.index(timestamp)
            return {name: values[idx] for name, values in self.feature_vector.items()}
        except ValueError:
            return None
    
    def slice(self, start_ts: int, end_ts: int) -> "UnifiedFeatureMatrix":
        start_idx = None
        end_idx = None
        
        for i, ts in enumerate(self.timestamps):
            if ts >= start_ts and start_idx is None:
                start_idx = i
            if ts <= end_ts:
                end_idx = i
        
        if start_idx is None or end_idx is None:
            return UnifiedFeatureMatrix(
                symbol=self.symbol,
                interval_ms=self.interval_ms,
                timestamps=[],
                feature_vector={},
                metadata={}
            )
        
        sliced_timestamps = self.timestamps[start_idx:end_idx+1]
        sliced_vector = {
            name: values[start_idx:end_idx+1]
            for name, values in self.feature_vector.items()
        }
        
        return UnifiedFeatureMatrix(
            symbol=self.symbol,
            interval_ms=self.interval_ms,
            timestamps=sliced_timestamps,
            feature_vector=sliced_vector,
            metadata=self.metadata
        )


class UnifiedMatrixBuilder:
    """统一特征矩阵构建器
    包含时间纪律信息，防止数据泄漏
    """
    
    def __init__(self, symbol: str, interval_ms: int = 60000):
        self.symbol = symbol
        self.interval_ms = interval_ms
        self.schema_registry = get_schema_registry()
        
        # 初始化特征向量
        self.timestamps: List[int] = []
        self.feature_vector: Dict[str, List[float]] = {}
        
        # 时间纪律字段
        self.feature_timestamps: Dict[str, List[int]] = {}
        self.available_ats: Dict[str, List[int]] = {}
        
        # 初始化所有特征为0
        for feature_name in self.schema_registry.get_all_feature_names():
            self.feature_vector[feature_name] = []
            self.feature_timestamps[feature_name] = []
            self.available_ats[feature_name] = []
    
    def set_timestamps(self, timestamps: List[int]):
        """设置时间戳序列"""
        self.timestamps = sorted(list(set(timestamps)))
        
        # 初始化所有特征列
        n = len(self.timestamps)
        for feature_name in self.feature_vector:
            self.feature_vector[feature_name] = [0.0] * n
            self.feature_timestamps[feature_name] = self.timestamps.copy()
            
            # 计算可用时间
            schema = self.schema_registry.get_schema(feature_name)
            available_after = schema.available_after_periods if schema else 0
            self.available_ats[feature_name] = [
                ts + (available_after * self.interval_ms)
                for ts in self.timestamps
            ]
    
    def add_feature_group(self, group_data: Dict[str, pd.DataFrame]):
        """添加特征组数据
        
        Args:
            group_data: {feature_name: df}，df有timestamp列和value列
        """
        if len(self.timestamps) == 0:
            # 自动从group_data收集时间戳
            all_ts = []
            for name, df in group_data.items():
                if df is not None and not df.empty:
                    if "timestamp" in df.columns:
                        all_ts.extend(df["timestamp"].tolist())
                    elif df.index.name == "timestamp":
                        all_ts.extend(df.index.tolist())
            if all_ts:
                self.set_timestamps(all_ts)
        
        for feature_name, df in group_data.items():
            if df is None or df.empty:
                continue
            
            if feature_name not in self.feature_vector:
                continue
            
            # 对齐并填充
            self._align_and_fill(feature_name, df)
    
    def _align_and_fill(self, feature_name: str, df: pd.DataFrame):
        """对齐并填充单个特征"""
        # 提取时间戳和值
        if "timestamp" in df.columns:
            ts_series = df["timestamp"]
            val_series = df.iloc[:, 0] if len(df.columns) > 1 else df[df.columns[0]]
        else:
            ts_series = df.index
            val_series = df.iloc[:, 0]
        
        # 创建时间戳到值的映射
        ts_to_val = dict(zip(ts_series, val_series))
        
        # 填充
        for i, target_ts in enumerate(self.timestamps):
            if target_ts in ts_to_val:
                self.feature_vector[feature_name][i] = float(ts_to_val[target_ts])
            elif i > 0:
                # 前向填充
                self.feature_vector[feature_name][i] = self.feature_vector[feature_name][i-1]
    
    def build(self) -> UnifiedFeatureMatrix:
        """构建统一特征矩阵"""
        return UnifiedFeatureMatrix(
            symbol=self.symbol,
            interval_ms=self.interval_ms,
            timestamps=self.timestamps,
            feature_vector=self.feature_vector,
            feature_timestamps=self.feature_timestamps,
            available_ats=self.available_ats,
            metadata={
                "generated_at": pd.Timestamp.now().isoformat(),
                "n_features": len(self.feature_vector),
                "n_timestamps": len(self.timestamps),
                "has_time_discipline": True
            }
        )

