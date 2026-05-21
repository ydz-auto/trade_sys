"""
Realtime Materializer - 实时特征矩阵生成器

核心功能：
- 滚动窗口特征计算
- 实时Vector更新
- FeatureMatrix流输出
"""

from typing import Dict, Optional, List
from collections import deque
from dataclasses import dataclass
import pandas as pd
import numpy as np
from datetime import datetime

from infrastructure.logging import get_logger
from domain.feature.materializer.matrix_builder import UnifiedFeatureMatrix
from domain.feature.materializer.schema_registry import get_schema_registry

logger = get_logger("feature.materializer.realtime")


@dataclass
class RealtimeFeatureUpdate:
    """实时特征更新"""
    timestamp: int
    feature_vector: Dict[str, float]


class RealtimeFeatureMaterializer:
    """实时特征矩阵生成器"""
    
    def __init__(
        self,
        symbol: str,
        interval_ms: int = 60000,
        window_size: int = 60
    ):
        self.symbol = symbol
        self.interval_ms = interval_ms
        self.window_size = window_size
        
        self.schema_registry = get_schema_registry()
        
        # 滚动窗口
        self.timestamp_window: deque = deque(maxlen=window_size)
        self.feature_window: Dict[str, deque] = {}
        
        # 初始化特征窗口
        for feature_name in self.schema_registry.get_all_feature_names():
            self.feature_window[feature_name] = deque(maxlen=window_size)
        
        # 最近一次完整更新
        self.last_complete_vector: Optional[Dict[str, float]] = None
    
    def update_trades(self, trades_df: pd.DataFrame):
        """更新Trade数据"""
        if trades_df.empty:
            return
        
        # 提取最新时间戳
        latest_ts = self._get_latest_timestamp(trades_df)
        if not latest_ts:
            return
        
        # 计算Trade特征 (简化版实时计算)
        trade_features = self._compute_realtime_trade_features(trades_df)
        
        self._update_feature_window(latest_ts, trade_features)
    
    def update_oi(self, oi_df: pd.DataFrame):
        """更新OI数据"""
        if oi_df.empty:
            return
        
        latest_ts = self._get_latest_timestamp(oi_df)
        if not latest_ts:
            return
        
        oi_features = self._compute_realtime_oi_features(oi_df)
        self._update_feature_window(latest_ts, oi_features)
    
    def update_funding(self, funding_df: pd.DataFrame):
        """更新Funding数据"""
        if funding_df.empty:
            return
        
        latest_ts = self._get_latest_timestamp(funding_df)
        if not latest_ts:
            return
        
        funding_features = self._compute_realtime_funding_features(funding_df)
        self._update_feature_window(latest_ts, funding_features)
    
    def update_liquidation(self, liq_df: pd.DataFrame):
        """更新Liquidation数据"""
        if liq_df.empty:
            return
        
        latest_ts = self._get_latest_timestamp(liq_df)
        if not latest_ts:
            return
        
        liq_features = self._compute_realtime_liq_features(liq_df)
        self._update_feature_window(latest_ts, liq_features)
    
    def _get_latest_timestamp(self, df: pd.DataFrame) -> Optional[int]:
        if "timestamp" in df.columns:
            return int(df["timestamp"].iloc[-1])
        elif df.index.name == "timestamp":
            return int(df.index[-1])
        return None
    
    def _compute_realtime_trade_features(self, trades_df: pd.DataFrame) -> Dict[str, float]:
        features = {}
        
        if "quantity" in trades_df.columns and "is_buyer_maker" in trades_df.columns:
            buy_qty = trades_df[~trades_df["is_buyer_maker"]]["quantity"].sum()
            sell_qty = trades_df[trades_df["is_buyer_maker"]]["quantity"].sum()
            
            features["trade_delta"] = buy_qty - sell_qty
            features["aggressive_buy_ratio"] = buy_qty / (buy_qty + sell_qty + 1e-8)
        
        return features
    
    def _compute_realtime_oi_features(self, oi_df: pd.DataFrame) -> Dict[str, float]:
        features = {}
        
        if "open_interest" in oi_df.columns:
            oi_values = oi_df["open_interest"].values
            if len(oi_values) >= 2:
                features["oi_delta"] = oi_values[-1] - oi_values[-2]
                
                if len(oi_values) >= 20:
                    mean = np.mean(oi_values[-20:])
                    std = np.std(oi_values[-20:]) + 1e-8
                    features["oi_zscore"] = (oi_values[-1] - mean) / std
        
        return features
    
    def _compute_realtime_funding_features(self, funding_df: pd.DataFrame) -> Dict[str, float]:
        features = {}
        
        if "funding_rate" in funding_df.columns:
            fr_values = funding_df["funding_rate"].values
            if len(fr_values) >= 20:
                mean = np.mean(fr_values[-20:])
                std = np.std(fr_values[-20:]) + 1e-8
                features["funding_zscore"] = (fr_values[-1] - mean) / std
        
        return features
    
    def _compute_realtime_liq_features(self, liq_df: pd.DataFrame) -> Dict[str, float]:
        features = {}
        
        if len(liq_df) > 0:
            features["liquidation_cluster"] = float(len(liq_df))
        
        return features
    
    def _update_feature_window(self, timestamp: int, features: Dict[str, float]):
        """更新特征窗口"""
        self.timestamp_window.append(timestamp)
        
        for feature_name in self.schema_registry.get_all_feature_names():
            value = features.get(feature_name, 0.0)
            self.feature_window[feature_name].append(value)
        
        # 累积计算
        self._compute_cumulative_features()
        
        # 保存完整向量
        self.last_complete_vector = self._get_current_vector()
    
    def _compute_cumulative_features(self):
        """计算累积特征"""
        if len(self.timestamp_window) < 2:
            return
        
        # cumulative_delta
        trade_deltas = list(self.feature_window["trade_delta"])
        if len(trade_deltas) > 0:
            self.feature_window["cumulative_delta"][-1] = sum(trade_deltas)
    
    def _get_current_vector(self) -> Dict[str, float]:
        """获取当前特征向量"""
        vector = {}
        
        for feature_name in self.schema_registry.get_all_feature_names():
            window = self.feature_window[feature_name]
            vector[feature_name] = window[-1] if len(window) > 0 else 0.0
        
        return vector
    
    def get_current_matrix(self) -> UnifiedFeatureMatrix:
        """获取当前滚动窗口特征矩阵"""
        timestamps = list(self.timestamp_window)
        
        feature_vector = {}
        for feature_name in self.schema_registry.get_all_feature_names():
            feature_vector[feature_name] = list(self.feature_window[feature_name])
        
        return UnifiedFeatureMatrix(
            symbol=self.symbol,
            interval_ms=self.interval_ms,
            timestamps=timestamps,
            feature_vector=feature_vector,
            metadata={"type": "realtime", "window_size": self.window_size}
        )
    
    def get_latest_update(self) -> Optional[RealtimeFeatureUpdate]:
        """获取最新特征更新"""
        if not self.last_complete_vector or len(self.timestamp_window) == 0:
            return None
        
        return RealtimeFeatureUpdate(
            timestamp=self.timestamp_window[-1],
            feature_vector=self.last_complete_vector
        )

