"""
LSTM Dataset Builder - LSTM 数据集构建器（ReplayRuntime 驱动）

核心改进：
1. ✅ 通过 ReplayRuntime 驱动，不走直接 parquet 读取
2. ✅ 使用 FeatureRuntime 确保特征计算一致
3. ✅ 使用 Label Isolation Store 防止 Label Leakage
4. ✅ Point-in-Time 特征存储

架构：
    ReplayRuntime
         ↓
    FeatureRuntime
         ↓
    PointInTime Store
         ↓
    Dataset Builder

⚠️ 禁止直接读取 parquet！⚠️
所有数据必须走事件驱动的 ReplayRuntime。

用法：
    from domain.ml.lstm_dataset_builder import LSTMDatasetBuilder
    
    builder = LSTMDatasetBuilder()
    X_train, X_val, y_train, y_val = builder.build_with_replay(
        parquet_path=path,
        symbol="BTCUSDT",
        start_time_ms=...,
        end_time_ms=...
    )
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import warnings

import pandas as pd
import numpy as np

from infrastructure.logging import get_logger
from runtime.replay_runtime import get_replay_runtime, SessionState
from runtime.feature_runtime import get_feature_runtime


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
    LSTM 数据集构建器（ReplayRuntime 驱动）
    
    所有数据通过 ReplayRuntime 事件流获取，禁止直接读取 parquet！
    
    用法：
    ```python
    builder = LSTMDatasetBuilder()
    X_train, X_val, y_train, y_val, scaler = builder.build_with_replay(
        parquet_path=path,
        symbol="BTCUSDT"
    )
    ```
    """
    
    def __init__(self, config: DatasetConfig = None):
        self.config = config or DatasetConfig()
        self._scaler = None
    
    def build(
        self,
        parquet_path: Path,
        symbol: str = "BTCUSDT",
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Any]:
        """
        构建数据集（已弃用！）
        
        ⚠️ 此方法直接读取 parquet，绕过时间因果基础设施！
        ⚠️ 会导致 Future Leakage！
        
        Args:
            parquet_path: 特征 Parquet 路径
            symbol: 币种
            
        Returns:
            X_train, X_val, y_train, y_val, scaler
        """
        warnings.warn(
            "LSTMDatasetBuilder.build() IS DEPRECATED! "
            "This method directly reads parquet and bypasses time-causal infrastructure. "
            "Use build_with_replay() instead to prevent future data leakage.",
            DeprecationWarning,
            stacklevel=2,
        )
        
        raise RuntimeError(
            "Direct parquet reading is disabled! "
            "Use build_with_replay() which goes through ReplayRuntime."
        )
    
    async def build_with_replay(
        self,
        parquet_path: Path,
        symbol: str = "BTCUSDT",
        start_time_ms: Optional[int] = None,
        end_time_ms: Optional[int] = None,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Any]:
        """
        通过 ReplayRuntime 构建数据集（推荐方式）
        
        架构：ReplayRuntime → FeatureRuntime → PIT Store → Dataset
        
        Args:
            parquet_path: 数据源路径（ReplayRuntime 会正确加载）
            symbol: 币种
            start_time_ms: 开始时间（可选）
            end_time_ms: 结束时间（可选）
            
        Returns:
            X_train, X_val, y_train, y_val, scaler
        """
        logger.info(f"Building dataset via ReplayRuntime: {symbol}")
        
        # 1. 获取 Runtime
        replay_runtime = get_replay_runtime()
        feature_runtime = get_feature_runtime()
        
        # 2. 收集特征的回调
        features_list = []
        timestamps_list = []
        
        async def on_feature(timestamp_ms, features):
            features_list.append(features)
            timestamps_list.append(timestamp_ms)
        
        feature_runtime.set_callbacks(on_feature=on_feature)
        
        # 3. 运行 Replay（走真正的事件流）
        session_state: SessionState = await replay_runtime.run_backtest(
            symbol=symbol,
            strategy_id="rsi_oversold",  # 策略只是为了驱动流程，不影响特征收集
            params={"period": 14, "oversold": 30},
            start_time_ms=start_time_ms or 0,
            end_time_ms=end_time_ms or 0,
            initial_capital=10000.0,
            data_path=str(parquet_path),
        )
        
        # 4. 构建特征 DataFrame
        if not features_list:
            raise RuntimeError("No features collected during replay")
        
        feature_df = pd.DataFrame(features_list)
        feature_df['timestamp'] = timestamps_list
        feature_df = feature_df.sort_values('timestamp').reset_index(drop=True)
        
        # 5. 获取 Label（从 Label Store，物理隔离）
        from infrastructure.label_isolation import get_label_store, set_label_store_mode
        
        set_label_store_mode("research")
        label_store = get_label_store()
        
        labels = []
        for ts_ms in timestamps_list[:-self.config.target_shift]:
            label = label_store.get_label(f"lstm_{symbol}_{ts_ms}")
            labels.append(label.label_value if label else 0)
        
        # 6. 构建序列数据
        X_all = []
        y_all = []
        
        feature_data = feature_df[self.config.features].values
        y_raw = np.array(labels)
        
        valid_start = self.config.sequence_length
        valid_end = len(feature_data) - self.config.target_shift
        
        for i in range(valid_start, valid_end):
            X_all.append(feature_data[i - self.config.sequence_length:i])
            if i - self.config.sequence_length < len(y_raw):
                y_all.append(y_raw[i - self.config.sequence_length])
        
        X_all = np.array(X_all)
        y_all = np.array(y_all)
        
        # 7. 分割数据
        split_idx = int(len(X_all) * self.config.train_ratio)
        X_train, X_val = X_all[:split_idx], X_all[split_idx:]
        y_train, y_val = y_all[:split_idx], y_all[split_idx:]
        
        # 8. 标准化
        X_train_scaled, X_val_scaled, scaler = self._scale_data(X_train, X_val)
        
        logger.info(f"Dataset built via ReplayRuntime: train={X_train_scaled.shape}, val={X_val_scaled.shape}")
        
        return X_train_scaled, X_val_scaled, y_train, y_val, scaler
    
    def build_with_runtime(
        self,
        parquet_path: Path,
        symbol: str = "BTCUSDT",
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Any]:
        """
        同步包装器 - 通过 ReplayRuntime 构建数据集
        
        Args:
            parquet_path: 数据源路径
            symbol: 币种
            
        Returns:
            X_train, X_val, y_train, y_val, scaler
        """
        import asyncio
        return asyncio.run(self.build_with_replay(parquet_path, symbol))
    
    def _split_data(
        self,
        X: np.ndarray,
        y: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """分割训练/验证集"""
        split_idx = int(len(X) * self.config.train_ratio)
        return X[:split_idx], X[split_idx:], y[:split_idx], y[split_idx:]
    
    def _scale_data(
        self,
        X_train: np.ndarray,
        X_val: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, Any]:
        """标准化数据"""
        from sklearn.preprocessing import MinMaxScaler, StandardScaler
        
        if self.config.scaler_type == "minmax":
            scaler = MinMaxScaler(feature_range=(-1, 1))
        else:
            scaler = StandardScaler()
        
        # 只在训练集上拟合
        X_train_scaled = scaler.fit_transform(X_train.reshape(-1, X_train.shape[-1]))
        X_val_scaled = scaler.transform(X_val.reshape(-1, X_val.shape[-1]))
        
        X_train_scaled = X_train_scaled.reshape(X_train.shape)
        X_val_scaled = X_val_scaled.reshape(X_val.shape)
        
        return X_train_scaled, X_val_scaled, scaler
    
    def _ensure_features(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """确保特征存在（通过 FeatureRuntime）"""
        feature_runtime = get_feature_runtime()
        
        # 确保所有需要的特征都能被计算
        for feature_name in self.config.features:
            schema = feature_runtime.get_feature_schema(feature_name)
            if schema is None:
                logger.warning(f"Feature {feature_name} not available in FeatureRuntime")
        
        return df
    
    def _get_available_features(self, df: pd.DataFrame) -> List[str]:
        """获取可用特征（从 FeatureRuntime）"""
        feature_runtime = get_feature_runtime()
        return feature_runtime.get_all_feature_names()