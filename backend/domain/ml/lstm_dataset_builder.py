"""
LSTM Dataset Builder - LSTM 数据集构建器

替代 scripts/train_lstm_strategy.py 中的数据准备逻辑

核心改进：
1. 使用 UnifiedFeatureCalculator 确保特征计算一致
2. 使用 FeatureAvailabilityGuard 防止数据泄漏
3. 统一的数据预处理流程

用法：
    from domain.ml.lstm_dataset_builder import LSTMDatasetBuilder
    
    builder = LSTMDatasetBuilder()
    X_train, X_val, y_train, y_val = builder.build_with_runtime(parquet_path)
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import warnings

import pandas as pd
import numpy as np

from infrastructure.logging import get_logger
from domain.feature.unified_calculator import UnifiedFeatureCalculator, get_feature_calculator

logger = get_logger("lstm_dataset_builder")


@dataclass
class DatasetConfig:
    """数据集配置"""
    sequence_length: int = 24
    target_shift: int = 12
    train_ratio: float = 0.8
    
    features: List[str] = field(default_factory=lambda: [
        'rsi_14', 'macd', 'macd_signal', 'volume_ratio',
        'funding_rate', 'funding_zscore', 'oi_delta',
        'bb_upper', 'bb_lower', 'momentum_10',
    ])
    
    target_column: str = "return_5m"
    enable_feature_guard: bool = True
    
    scaler_type: str = "minmax"


class LSTMDatasetBuilder:
    """
    LSTM 数据集构建器
    
    使用 UnifiedFeatureCalculator 确保特征计算一致。
    
    用法：
    ```python
    builder = LSTMDatasetBuilder()
    X_train, X_val, y_train, y_val, scaler = builder.build_with_runtime(parquet_path)
    ```
    """
    
    def __init__(self, config: DatasetConfig = None):
        self.config = config or DatasetConfig()
        self.calculator = get_feature_calculator()
        self._scaler = None
        self._feature_guard = None
    
    def build(
        self,
        parquet_path: Path,
        symbol: str = "BTCUSDT",
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Any]:
        """
        构建数据集（已弃用，不经过时间因果基础设施）
        
        Args:
            parquet_path: 特征 Parquet 路径
            symbol: 币种
            
        Returns:
            X_train, X_val, y_train, y_val, scaler
        """
        warnings.warn(
            "LSTMDatasetBuilder.build() bypasses the time-causal infrastructure "
            "(feature_matrix_runtime, Point-in-Time store, feature availability guard). "
            "Use build_with_runtime() instead to prevent future data leakage.",
            DeprecationWarning,
            stacklevel=2,
        )
        
        df = pd.read_parquet(parquet_path)
        
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        df = self._ensure_features(df, symbol)
        
        available_features = self._get_available_features(df)
        
        X_all, y_all = self._create_sequences(df, available_features)
        
        X_train, X_val, y_train, y_val = self._split_data(X_all, y_all)
        
        X_train_scaled, X_val_scaled, scaler = self._scale_data(X_train, X_val)
        
        logger.info(f"Dataset built: train={X_train_scaled.shape}, val={X_val_scaled.shape}")
        
        return X_train_scaled, X_val_scaled, y_train, y_val, scaler
    
    def build_with_runtime(
        self,
        parquet_path: Path,
        symbol: str = "BTCUSDT",
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Any]:
        from runtime.feature_matrix_runtime import TimeCausalFeatureMatrix, get_feature_matrix_runtime
        from infrastructure.storage.point_in_time_store import FeatureSourceType
        from infrastructure.label_isolation import StrictLabelStore, get_label_store, set_label_store_mode
        
        # 1. 设置 Label Store 模式（Research 模式可以访问 Label）
        set_label_store_mode("research")
        label_store = get_label_store()
        
        df = pd.read_parquet(parquet_path)
        
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        df = self._ensure_features(df, symbol)
        
        available_features = self._get_available_features(df)
        
        runtime = get_feature_matrix_runtime(symbol, mode="replay")
        pit_store = runtime._pit_store
        
        timestamps_ms = []
        for idx, row in df.iterrows():
            if 'timestamp' in df.columns:
                ts_val = row['timestamp']
                if isinstance(ts_val, pd.Timestamp):
                    ts_ms = int(ts_val.timestamp() * 1000)
                else:
                    ts_ms = int(pd.Timestamp(ts_val).timestamp() * 1000)
            else:
                ts_ms = int(idx) * 60000
            timestamps_ms.append(ts_ms)
        
        # 2. 存储特征到 Point-in-Time Store
        for i, row in df.iterrows():
            ts_ms = timestamps_ms[i]
            feature_dict = {}
            for feat in available_features:
                val = row[feat]
                if pd.notna(val):
                    feature_dict[feat] = float(val)
            if feature_dict:
                pit_store.store_features_batch(
                    features=feature_dict,
                    feature_timestamp=ts_ms,
                    source_types={feat: FeatureSourceType.AGGREGATED for feat in feature_dict},
                )
        
        # 3. 存储 Label 到 Label Store（物理隔离）
        for i in range(len(df) - self.config.target_shift):
            ts_ms = timestamps_ms[i]
            target_ts_ms = timestamps_ms[i + self.config.target_shift]
            
            if self.config.target_column in df.columns:
                target_val = df.iloc[i + self.config.target_shift][self.config.target_column]
            else:
                close_now = df.iloc[i]['close']
                close_future = df.iloc[i + self.config.target_shift]['close']
                target_val = (close_future - close_now) / close_now if close_now != 0 else 0
            
            label_store.store_label(
                label_id=f"lstm_{symbol}_{ts_ms}",
                label_value=int(target_val > 0) if self.config.target_column else target_val,
                label_timestamp=target_ts_ms,
                feature_timestamp=ts_ms,
                source="dataset_builder"
            )
        
        feature_rows = []
        y_all = []
        
        valid_start = self.config.sequence_length
        valid_end = len(df) - self.config.target_shift
        
        for i in range(valid_start, valid_end):
            ts_ms = timestamps_ms[i]
            runtime.advance_to(ts_ms)
            snapshot = pit_store.get_features_at_time(ts_ms, feature_names=available_features)
            row_features = {feat: snapshot.features.get(feat, 0.0) for feat in available_features}
            feature_rows.append(row_features)
            
            # 4. 从 Label Store 读取（物理隔离确保安全）
            label = label_store.get_label(f"lstm_{symbol}_{ts_ms}")
            y_all.append(label.label_value if label else 0)
        
        feature_df = pd.DataFrame(feature_rows, columns=available_features).fillna(0.0)
        feature_data = feature_df.values
        
        X_all = []
        y_arr = np.array(y_all)
        
        for i in range(len(feature_data) - self.config.sequence_length + 1):
            X_all.append(feature_data[i:i + self.config.sequence_length])
        
        if len(X_all) > len(y_arr):
            X_all = X_all[:len(y_arr)]
        
        X_all = np.array(X_all)
        y_all = np.array(y_arr)[:len(X_all)]
        
        X_train, X_val, y_train, y_val = self._split_data(X_all, y_all)
        
        X_train_scaled, X_val_scaled, scaler = self._scale_data(X_train, X_val)
        
        logger.info(f"Dataset built with runtime: train={X_train_scaled.shape}, val={X_val_scaled.shape}")
        
        return X_train_scaled, X_val_scaled, y_train, y_val, scaler
    
    def build_with_feature_guard(
        self,
        parquet_path: Path,
        symbol: str = "BTCUSDT",
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Any]:
        """
        构建数据集（带特征可用性检查）
        
        使用 feature_matrix_runtime + Point-in-Time Store 防止数据泄漏。
        """
        return self.build_with_runtime(parquet_path, symbol)
    
    def _ensure_features(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """确保所有特征都存在"""
        for feature in self.config.features:
            if feature not in df.columns:
                df[feature] = 0.0
        
        if self.config.target_column not in df.columns:
            if 'close' in df.columns:
                df[self.config.target_column] = df['close'].pct_change()
        
        return df
    
    def _get_available_features(self, df: pd.DataFrame) -> List[str]:
        """获取可用特征"""
        available = []
        for feature in self.config.features:
            if feature in df.columns:
                available.append(feature)
        return available
    
    def _create_sequences(
        self,
        df: pd.DataFrame,
        features: List[str],
    ) -> Tuple[np.ndarray, np.ndarray]:
        """创建序列"""
        feature_data = df[features].fillna(0).values
        
        if self.config.target_column in df.columns:
            target = df[self.config.target_column].shift(-self.config.target_shift)
            y_raw = (target > 0).astype(int).values
        else:
            target = df['close'].pct_change().shift(-self.config.target_shift)
            y_raw = (target > 0).astype(int).values
        
        valid_start = self.config.sequence_length
        valid_end = len(df) - self.config.target_shift
        
        X_all = []
        y_all = []
        
        for i in range(valid_start, valid_end):
            X_all.append(feature_data[i-self.config.sequence_length:i])
            y_all.append(y_raw[i])
        
        return np.array(X_all), np.array(y_all)
    
    def _split_data(
        self,
        X_all: np.ndarray,
        y_all: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """分割数据"""
        train_size = int(self.config.train_ratio * len(X_all))
        
        X_train = X_all[:train_size]
        X_val = X_all[train_size:]
        y_train = y_all[:train_size]
        y_val = y_all[train_size:]
        
        return X_train, X_val, y_train, y_val
    
    def _scale_data(
        self,
        X_train: np.ndarray,
        X_val: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, Any]:
        """标准化数据"""
        if self.config.scaler_type == "minmax":
            from sklearn.preprocessing import MinMaxScaler
            self._scaler = MinMaxScaler()
        else:
            from sklearn.preprocessing import StandardScaler
            self._scaler = StandardScaler()
        
        n_train_samples, seq_len, n_features = X_train.shape
        X_train_reshaped = X_train.reshape(-1, n_features)
        
        self._scaler.fit(X_train_reshaped)
        
        X_train_scaled = self._scaler.transform(X_train_reshaped).reshape(n_train_samples, seq_len, n_features)
        
        n_val_samples = X_val.shape[0]
        X_val_reshaped = X_val.reshape(-1, n_features)
        X_val_scaled = self._scaler.transform(X_val_reshaped).reshape(n_val_samples, seq_len, n_features)
        
        return X_train_scaled, X_val_scaled, self._scaler
    
    def get_feature_importance(self) -> Dict[str, float]:
        """获取特征重要性"""
        return {feature: 1.0 / len(self.config.features) for feature in self.config.features}


def build_lstm_dataset(
    parquet_path: Path,
    config: DatasetConfig = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Any]:
    """
    便捷函数：构建 LSTM 数据集
    
    替代 train_lstm_strategy.py 中的 prepare_training_data
    """
    builder = LSTMDatasetBuilder(config)
    return builder.build_with_runtime(parquet_path)
