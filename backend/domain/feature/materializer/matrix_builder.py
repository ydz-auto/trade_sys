"""
Matrix Builder - 统一特征矩阵构建器

核心功能：
- 基于6大Feature Group构建timestamp × feature_vector矩阵
- 标准化特征值
- 缺失值处理

加速：
- 多线程并行处理特征组对齐填充
- GPU Tensor 批量前向填充（大数据量时）
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import numpy as np

from domain.logging import get_logger
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
    
    加速策略：
    - add_feature_group() 多线程并行对齐填充
    - _align_and_fill_batch_gpu() GPU 批量前向填充（大数据量）
    """
    
    def __init__(self, symbol: str, interval_ms: int = 60000, n_workers: int = 4, accelerator=None):
        self.symbol = symbol
        self.interval_ms = interval_ms
        self.schema_registry = get_schema_registry()
        self.n_workers = n_workers
        self._accelerator = accelerator
        
        self.timestamps: List[int] = []
        self.feature_vector: Dict[str, List[float]] = {}
        
        self.feature_timestamps: Dict[str, List[int]] = {}
        self.available_ats: Dict[str, List[int]] = {}
        
        self._gpu_available = False
        self._init_gpu()
        
        for feature_name in self.schema_registry.get_all_feature_names():
            self.feature_vector[feature_name] = []
            self.feature_timestamps[feature_name] = []
            self.available_ats[feature_name] = []
    
    def _init_gpu(self):
        if self._accelerator is not None:
            try:
                self._gpu_available = self._accelerator.is_gpu_available()
            except Exception:
                self._gpu_available = False
        else:
            try:
                from infrastructure.acceleration import is_gpu_available
                self._gpu_available = is_gpu_available()
            except Exception:
                self._gpu_available = False
    
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
        """添加特征组数据（多线程并行对齐填充）
        
        Args:
            group_data: {feature_name: df}，df有timestamp列和value列
        """
        if len(self.timestamps) == 0:
            all_ts = []
            for name, df in group_data.items():
                if df is not None and not df.empty:
                    if "timestamp" in df.columns:
                        all_ts.extend(df["timestamp"].tolist())
                    elif df.index.name == "timestamp":
                        all_ts.extend(df.index.tolist())
            if all_ts:
                self.set_timestamps(all_ts)
        
        valid_items = {
            name: df for name, df in group_data.items()
            if df is not None and not df.empty and name in self.feature_vector
        }
        
        if not valid_items:
            return
        
        if len(valid_items) > 1 and self.n_workers > 1:
            self._add_feature_group_parallel(valid_items)
        else:
            for feature_name, df in valid_items.items():
                self._align_and_fill(feature_name, df)
    
    def _add_feature_group_parallel(self, group_data: Dict[str, pd.DataFrame]):
        """多线程并行对齐填充"""
        with ThreadPoolExecutor(max_workers=min(self.n_workers, len(group_data))) as executor:
            futures = {}
            for feature_name, df in group_data.items():
                futures[executor.submit(
                    self._align_and_fill_return, feature_name, df
                )] = feature_name
            
            for future in as_completed(futures):
                feature_name = futures[future]
                try:
                    aligned_values = future.result()
                    self.feature_vector[feature_name] = aligned_values
                except Exception as e:
                    logger.warning(f"Parallel align failed for {feature_name}: {e}")
    
    def _align_and_fill_return(self, feature_name: str, df: pd.DataFrame) -> List[float]:
        """对齐并填充，返回结果列表（线程安全，不修改 self）"""
        if "timestamp" in df.columns:
            ts_series = df["timestamp"]
            val_series = df.iloc[:, 0] if len(df.columns) > 1 else df[df.columns[0]]
        else:
            ts_series = df.index
            val_series = df.iloc[:, 0]
        
        ts_to_val = dict(zip(ts_series, val_series))
        
        n = len(self.timestamps)
        if n == 0:
            return []
        
        values = [0.0] * n
        
        if self._gpu_available and n > 10000:
            values = self._align_and_fill_gpu(ts_to_val, n)
        else:
            for i, target_ts in enumerate(self.timestamps):
                if target_ts in ts_to_val:
                    values[i] = float(ts_to_val[target_ts])
                elif i > 0:
                    values[i] = values[i - 1]
        
        return values
    
    def _align_and_fill_gpu(
        self, ts_to_val: Dict, n: int
    ) -> List[float]:
        """GPU 批量前向填充（大数据量时使用）"""
        try:
            if self._accelerator is not None:
                torch = self._accelerator.torch
                device = self._accelerator.device
                to_gpu = self._accelerator.to_gpu
                to_cpu = self._accelerator.to_cpu
            else:
                from infrastructure.acceleration import torch, device, to_gpu, to_cpu
            
            ts_array = np.array(self.timestamps, dtype=np.int64)
            ts_tensor = to_gpu(ts_array)
            
            values_array = np.zeros(n, dtype=np.float32)
            for i, target_ts in enumerate(self.timestamps):
                if target_ts in ts_to_val:
                    values_array[i] = float(ts_to_val[target_ts])
            
            values_tensor = to_gpu(values_array)
            
            mask = values_tensor != 0
            
            nonzero_indices = torch.nonzero(mask, as_tuple=True)[0]
            
            if len(nonzero_indices) > 0:
                for i in range(1, n):
                    if not mask[i]:
                        values_tensor[i] = values_tensor[i - 1]
            
            return to_cpu(values_tensor).tolist()
        except Exception as e:
            logger.warning(f"GPU align_and_fill failed, falling back to CPU: {e}")
            values = [0.0] * n
            for i, target_ts in enumerate(self.timestamps):
                if target_ts in ts_to_val:
                    values[i] = float(ts_to_val[target_ts])
                elif i > 0:
                    values[i] = values[i - 1]
            return values
    
    def _align_and_fill(self, feature_name: str, df: pd.DataFrame):
        """对齐并填充单个特征"""
        if "timestamp" in df.columns:
            ts_series = df["timestamp"]
            val_series = df.iloc[:, 0] if len(df.columns) > 1 else df[df.columns[0]]
        else:
            ts_series = df.index
            val_series = df.iloc[:, 0]
        
        ts_to_val = dict(zip(ts_series, val_series))
        
        for i, target_ts in enumerate(self.timestamps):
            if target_ts in ts_to_val:
                self.feature_vector[feature_name][i] = float(ts_to_val[target_ts])
            elif i > 0:
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

