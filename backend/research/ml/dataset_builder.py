from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import warnings

import pandas as pd
import numpy as np

import logging


logger = logging.getLogger(__name__)


@dataclass
class DatasetConfig:
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
    def __init__(self, config: DatasetConfig = None, replay_runtime=None, feature_runtime=None):
        self.config = config or DatasetConfig()
        self._scaler = None
        self._replay_runtime = replay_runtime
        self._feature_runtime = feature_runtime

    def build(
        self,
        parquet_path: Path,
        symbol: str = "BTCUSDT",
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Any]:
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
        logger.info(f"Building dataset via ReplayRuntime: {symbol}")

        if self._replay_runtime is None:
            raise ValueError("replay_runtime must be provided via constructor")
        if self._feature_runtime is None:
            raise ValueError("feature_runtime must be provided via constructor")

        replay_runtime = self._replay_runtime
        feature_runtime = self._feature_runtime

        features_list = []
        timestamps_list = []

        async def on_feature(timestamp_ms, features):
            features_list.append(features)
            timestamps_list.append(timestamp_ms)

        feature_runtime.set_callbacks(on_feature=on_feature)

        session_state = await replay_runtime.run_backtest(
            symbol=symbol,
            strategy_id="rsi_oversold",
            params={"period": 14, "oversold": 30},
            start_time_ms=start_time_ms or 0,
            end_time_ms=end_time_ms or 0,
            initial_capital=10000.0,
            data_path=str(parquet_path),
        )

        if not features_list:
            raise RuntimeError("No features collected during replay")

        feature_df = pd.DataFrame(features_list)
        feature_df['timestamp'] = timestamps_list
        feature_df = feature_df.sort_values('timestamp').reset_index(drop=True)

        from domain.feature.label_isolation import get_label_store, set_label_store_mode

        set_label_store_mode("research")
        label_store = get_label_store()

        labels = []
        for ts_ms in timestamps_list[:-self.config.target_shift]:
            label = label_store.get_label(f"lstm_{symbol}_{ts_ms}")
            labels.append(label.label_value if label else 0)

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

        split_idx = int(len(X_all) * self.config.train_ratio)
        X_train, X_val = X_all[:split_idx], X_all[split_idx:]
        y_train, y_val = y_all[:split_idx], y_all[split_idx:]

        X_train_scaled, X_val_scaled, scaler = self._scale_data(X_train, X_val)

        logger.info(f"Dataset built via ReplayRuntime: train={X_train_scaled.shape}, val={X_val_scaled.shape}")

        return X_train_scaled, X_val_scaled, y_train, y_val, scaler

    def build_with_runtime(
        self,
        parquet_path: Path,
        symbol: str = "BTCUSDT",
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Any]:
        import asyncio
        return asyncio.run(self.build_with_replay(parquet_path, symbol))

    def _split_data(
        self,
        X: np.ndarray,
        y: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        split_idx = int(len(X) * self.config.train_ratio)
        return X[:split_idx], X[split_idx:], y[:split_idx], y[split_idx:]

    def _scale_data(
        self,
        X_train: np.ndarray,
        X_val: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, Any]:
        from sklearn.preprocessing import MinMaxScaler, StandardScaler

        if self.config.scaler_type == "minmax":
            scaler = MinMaxScaler(feature_range=(-1, 1))
        else:
            scaler = StandardScaler()

        X_train_scaled = scaler.fit_transform(X_train.reshape(-1, X_train.shape[-1]))
        X_val_scaled = scaler.transform(X_val.reshape(-1, X_val.shape[-1]))

        X_train_scaled = X_train_scaled.reshape(X_train.shape)
        X_val_scaled = X_val_scaled.reshape(X_val.shape)

        return X_train_scaled, X_val_scaled, scaler

    def _ensure_features(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        if self._feature_runtime is None:
            raise ValueError("feature_runtime must be provided via constructor")
        feature_runtime = self._feature_runtime

        for feature_name in self.config.features:
            schema = feature_runtime.get_feature_schema(feature_name)
            if schema is None:
                logger.warning(f"Feature {feature_name} not available in FeatureRuntime")

        return df

    def _get_available_features(self, df: pd.DataFrame) -> List[str]:
        if self._feature_runtime is None:
            raise ValueError("feature_runtime must be provided via constructor")
        return self._feature_runtime.get_all_feature_names()
