"""
Feature Matrix v2 - 时间因果一致的特征矩阵

重构说明：
1. 使用 Runtime Clock 作为唯一时间源
2. 特征和 Label 严格物理隔离
3. 使用 Systematic Availability Guard
4. 使用 Point-in-Time Store 存储
5. 支持 Replay 和 Live 一致性验证
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import pandas as pd
import numpy as np
from pathlib import Path

from infrastructure.logging import get_logger
from infrastructure import (
    get_clock, set_clock_mode, ClockMode,
    get_systematic_guard,
    get_label_store, set_label_store_mode,
    safe_dataframe, assert_safe_dataframe,
    get_point_in_time_store,
    get_warmup_manager,
    get_feature_lineage, register_feature_lineage
)

logger = get_logger("feature_matrix_v2")


class FeatureCategory(str, Enum):
    """特征分类枚举"""
    RAW = "raw"
    DERIVED = "derived"
    MICROSTRUCTURE = "microstructure"
    CROSS_MARKET = "cross_market"
    EVENT = "event"


@dataclass
class FeatureMetadata:
    """特征元数据"""
    name: str
    name_en: str
    category: FeatureCategory
    description: str
    data_type: str = "float"
    normalization_range: Optional[tuple] = None
    zscore_window: int = 288
    is_factor: bool = False
    source: str = "internal"
    default_weight: float = 1.0
    last_updated: datetime = field(default_factory=datetime.now)


class TimeCausalFeatureMatrix:
    """
    时间因果一致的特征矩阵

    核心原则：
    1. 单一时间源：通过 get_clock() 获取时间
    2. 物理隔离：特征和 Label 完全分离
    3. 可验证性：支持 Replay 和 Live 一致性
    4. 可追溯性：特征血缘完整记录
    """

    FEATURE_METADATA: Dict[str, FeatureMetadata] = {}

    def __init__(self, symbol: str, mode: str = "replay"):
        self.symbol = symbol
        self.mode = mode

        self._clock = get_clock()
        self._guard = get_systematic_guard()
        self._label_store = get_label_store()
        self._pit_store = get_point_in_time_store(symbol)
        self._warmup = get_warmup_manager()
        self._lineage = get_feature_lineage()

        self._register_default_features()
        self._initialize_mode(mode)

        self._df: Optional[pd.DataFrame] = None

        logger.info(f"TimeCausalFeatureMatrix initialized for {symbol}, mode={mode}")

    def _register_default_features(self):
        """注册默认特征（同时在 Feature Lineage 和 Availability Guard 中注册）"""

        features = {
            "open": FeatureMetadata(
                "开盘价", "Open", FeatureCategory.RAW, "K线开盘价", "float"
            ),
            "high": FeatureMetadata(
                "最高价", "High", FeatureCategory.RAW, "K线最高价", "float"
            ),
            "low": FeatureMetadata(
                "最低价", "Low", FeatureCategory.RAW, "K线最低价", "float"
            ),
            "close": FeatureMetadata(
                "收盘价", "Close", FeatureCategory.RAW, "K线收盘价", "float"
            ),
            "volume": FeatureMetadata(
                "成交量", "Volume", FeatureCategory.RAW, "K线成交量", "float"
            ),
            "spread": FeatureMetadata(
                "买卖价差", "Spread", FeatureCategory.MICROSTRUCTURE, "最优买卖价差", "float"
            ),
            "imbalance_5": FeatureMetadata(
                "5档订单簿失衡", "Imbalance_5", FeatureCategory.MICROSTRUCTURE, "5档买卖量失衡", "float"
            ),
        }

        for name, meta in features.items():
            self.FEATURE_METADATA[name] = meta

            register_feature_lineage(
                feature_name=name,
                feature_type=meta.category.value,
                description=meta.description,
                dependencies=[]
            )

    def _initialize_mode(self, mode: str):
        """根据模式初始化"""
        if mode == "replay":
            set_clock_mode(ClockMode.REPLAY)
            set_label_store_mode("research")
        elif mode == "live":
            set_clock_mode(ClockMode.LIVE)
            set_label_store_mode("runtime")
        elif mode == "paper":
            set_clock_mode(ClockMode.PAPER)
            set_label_store_mode("runtime")

    def load_from_parquet(self, file_path: Path):
        """从 parquet 加载特征数据"""
        self._df = pd.read_parquet(file_path)
        self._df = safe_dataframe(self._df)
        logger.info(f"Loaded {len(self._df)} rows from {file_path}")

    def advance_to(self, timestamp_ms: int):
        """推进时钟到指定时间"""
        self._clock.advance_to(timestamp_ms)

    def get_features_at_time(self, timestamp_ms: int, feature_names: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        安全获取指定时间点的特征（时间因果一致）

        Args:
            timestamp_ms: 查询时间
            feature_names: 特征列表，None 表示全部

        Returns:
            特征字典
        """
        if self._df is None:
            return {}

        current_time = self._clock.available_at_ms()
        if timestamp_ms > current_time:
            logger.warning(f"Attempted to access future feature: {timestamp_ms} > {current_time}")
            return {}

        features = {}

        if feature_names is None:
            feature_names = list(self.FEATURE_METADATA.keys())

        for name in feature_names:
            is_available, _ = self._guard.check(name, timestamp_ms, current_time, self._clock)
            if is_available:
                features[name] = self._get_feature_value(name, timestamp_ms)

        return features

    def _get_feature_value(self, name: str, timestamp_ms: int) -> Any:
        """获取单个特征值（内部使用）"""
        if self._df is None or name not in self._df.columns:
            return None

        idx = self._df.index[self._df["timestamp"] <= timestamp_ms].max()
        if np.isnan(idx):
            return None

        return self._df.loc[idx, name]

    def compute_derived_feature(self, feature_name: str, data: Dict[str, Any]) -> Any:
        """
        计算衍生特征（带血缘记录）

        Args:
            feature_name: 特征名称
            data: 输入数据

        Returns:
            特征值
        """
        dependencies = []

        if feature_name == "volatility_1h":
            if "close" in data:
                dependencies.append("close")
                result = self._compute_volatility(data["close"], 12)
            else:
                result = None
        elif feature_name == "zscore_1h":
            if "close" in data:
                dependencies.append("close")
                result = self._compute_zscore(data["close"], 12)
            else:
                result = None
        else:
            result = None

        if dependencies and feature_name not in self._lineage._nodes:
            register_feature_lineage(
                feature_name=feature_name,
                feature_type="derived",
                dependencies=dependencies
            )

        return result

    def _compute_volatility(self, price_data: pd.Series, window: int) -> float:
        """计算波动率（仅使用历史）"""
        if len(price_data) < window:
            return np.nan
        return price_data.pct_change().iloc[-window:].std()

    def _compute_zscore(self, price_data: pd.Series, window: int) -> float:
        """计算 zscore（仅使用历史）"""
        if len(price_data) < window:
            return np.nan
        recent = price_data.iloc[-window:]
        mean = recent.mean()
        std = recent.std() + 1e-8
        return (price_data.iloc[-1] - mean) / std

    def add_label(self, label_name: str, timestamp_ms: int, value: Any, horizon_minutes: int = 60):
        """
        添加 Label（严格隔离）

        Args:
            label_name: Label 名称
            timestamp_ms: 时间戳
            value: Label 值
            horizon_minutes: 预测时长（分钟）
        """
        from infrastructure.label_isolation import LabelType

        self._label_store.store_label(
            label_id=label_name,
            label_type=LabelType.FUTURE_RETURN,
            timestamp=timestamp_ms,
            value=value,
            horizon_periods=horizon_minutes
        )

    def get_dataset_for_training(
        self,
        start_time: int,
        end_time: int,
        feature_names: List[str] = None
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """
        构建训练数据集（时间因果一致）

        Returns:
            (X: 特征 DataFrame, y: 标签 Series)
        """
        set_label_store_mode("research")

        X_list = []
        y_list = []

        timestamps = self._df[
            (self._df["timestamp"] >= start_time) &
            (self._df["timestamp"] <= end_time)
        ]["timestamp"].values

        for ts in timestamps:
            features = self.get_features_at_time(ts, feature_names)
            label = self._label_store.get_label("future_return_1h", ts)

            X_list.append(features)
            y_list.append(label)

        X = pd.DataFrame(X_list)
        y = pd.Series(y_list, name="target")

        return X, y

    def save_snapshot(self, snapshot_id: str):
        """保存特征快照（用于一致性验证）"""
        from infrastructure.storage.immutable_snapshot import create_immutable_snapshot

        current_time = self._clock.available_at_ms()
        features = self.get_features_at_time(current_time)

        snapshot = create_immutable_snapshot(
            features=features,
            snapshot_id=snapshot_id,
            metadata={"symbol": self.symbol, "mode": self.mode}
        )

        logger.info(f"Saved snapshot: {snapshot_id}")
        return snapshot

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        stat_dict = {
            "clock": self._clock.get_statistics(),
            "guard": self._guard.get_violation_report(),
            "labels": self._label_store.get_statistics(),
            "lineage": self._lineage.get_stats(),
        }

        if self._df is not None:
            stat_dict["data"] = {
                "rows": len(self._df),
                "features": len(self._df.columns)
            }

        return stat_dict


def create_time_causal_matrix(
    symbol: str,
    mode: str = "replay",
    parquet_path: Optional[str] = None
) -> TimeCausalFeatureMatrix:
    """创建时间因果一致的特征矩阵（工厂函数）"""
    matrix = TimeCausalFeatureMatrix(symbol, mode)

    if parquet_path:
        matrix.load_from_parquet(Path(parquet_path))

    return matrix
