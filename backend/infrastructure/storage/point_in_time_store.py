"""
Point-In-Time Feature Store - 时间点特征存储

核心功能：
1. 只允许 timestamp <= current_runtime_time 的数据进入
2. 记录每个特征的 available_at 时间
3. 防止未来数据泄漏
4. 支持 Replay 和 Live 的一致性

关键概念：
- feature_timestamp: 特征计算的时间戳（源数据时间）
- available_at: 特征可以被使用的时间戳（通常 >= feature_timestamp）
- replay_clock: 回播/策略执行的当前时间戳

使用场景：
- Replay Runtime: 按时间点获取可用特征
- Live Runtime: 确保特征延迟正确
- 训练数据生成: 防止 label contamination
"""

from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import pandas as pd
import numpy as np
from pathlib import Path
import json
import hashlib

from infrastructure.logging import get_logger

logger = get_logger("storage.point_in_time_store")


class FeatureSourceType(Enum):
    """特征来源类型"""
    INSTANT = "instant"  # 即时特征（spread, trade_delta）
    AGGREGATED = "aggregated"  # 聚合特征（volatility_1h）
    DERIVED = "derived"  # 衍生特征（funding_zscore）
    LABEL = "label"  # 标签（future_return）- 最高风险


@dataclass
class PointInTimeFeatureRecord:
    """时间点特征记录"""
    feature_name: str
    feature_timestamp: int  # 特征计算时间
    available_at: int  # 可用时间
    value: Any
    source_type: FeatureSourceType
    symbol: str
    delay_ms: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_available_at(self, query_time: int) -> bool:
        """检查在指定时间是否可用"""
        return query_time >= self.available_at
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature_name": self.feature_name,
            "feature_timestamp": self.feature_timestamp,
            "available_at": self.available_at,
            "value": self.value,
            "source_type": self.source_type.value,
            "symbol": self.symbol,
            "delay_ms": self.delay_ms,
            "metadata": self.metadata,
        }


@dataclass
class PointInTimeSnapshot:
    """时间点快照"""
    snapshot_timestamp: int
    symbol: str
    features: Dict[str, Any]
    feature_timestamps: Dict[str, int]
    available_at_times: Dict[str, int]
    blocked_features: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_timestamp": self.snapshot_timestamp,
            "symbol": self.symbol,
            "features": self.features,
            "feature_timestamps": self.feature_timestamps,
            "available_at_times": self.available_at_times,
            "blocked_features": self.blocked_features,
        }


class PointInTimeFeatureStore:
    """
    Point-In-Time Feature Store
    
    核心原则：
    1. 当前K线只能使用已关闭的历史K线数据
    2. 多周期聚合特征必须等待周期结束
    3. Label 必须严格隔离，不能进入特征
    4. 所有查询必须带时间戳，只返回该时间点可用的特征
    """
    
    LABEL_FEATURES: Set[str] = {
        "future_return", "future_return_1h", "future_return_4h",
        "future_high", "future_low", "future_max_drawdown",
        "target", "label", "y",
    }
    
    def __init__(
        self,
        symbol: str,
        interval_ms: int = 60000,
        feature_availability_guard=None,
    ):
        self.symbol = symbol
        self.interval_ms = interval_ms
        self._feature_availability_guard = feature_availability_guard
        
        self._records: Dict[int, Dict[str, PointInTimeFeatureRecord]] = {}
        self._feature_index: Dict[str, List[int]] = {}
        
        self._label_store: Dict[int, Dict[str, Any]] = {}
        
        self._access_log: List[Dict[str, Any]] = []
        self._leakage_attempts: List[Dict[str, Any]] = []
        
        self._strict_mode = True
        self._log_access = True

    def _get_guard(self):
        guard = self._feature_availability_guard
        if guard is None:
            # ARCHITECTURE NOTE: infrastructure → runtime 反向依赖
            # TODO: 应改为依赖注入，由调用方传入 FeatureAvailabilityGuard
            from runtimes.replay_runtime.shared_replay.feature_availability_guard import (
                FeatureAvailabilityGuard,
                get_feature_availability_guard,
            )
            guard = get_feature_availability_guard(self.interval_ms)
            self._feature_availability_guard = guard
        return guard
        
    def store_feature(
        self,
        feature_name: str,
        value: Any,
        feature_timestamp: int,
        available_at: Optional[int] = None,
        source_type: FeatureSourceType = FeatureSourceType.INSTANT,
        delay_ms: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PointInTimeFeatureRecord:
        """
        存储特征
        
        Args:
            feature_name: 特征名称
            value: 特征值
            feature_timestamp: 特征计算时间戳
            available_at: 可用时间戳（如果为None则自动计算）
            source_type: 特征来源类型
            delay_ms: 延迟毫秒数
            metadata: 元数据
        """
        if feature_name in self.LABEL_FEATURES:
            if feature_timestamp not in self._label_store:
                self._label_store[feature_timestamp] = {}
            self._label_store[feature_timestamp][feature_name] = value
            logger.debug(f"Stored label {feature_name} at {feature_timestamp} (isolated)")
            return None
        
        if available_at is None:
            available_at = self._get_guard().get_feature_available_at(feature_name, feature_timestamp)
        
        if delay_ms is None:
            rule = self._get_guard()._rules.get(feature_name)
            delay_ms = rule.delay_ms if rule else 0
        
        record = PointInTimeFeatureRecord(
            feature_name=feature_name,
            feature_timestamp=feature_timestamp,
            available_at=available_at,
            value=value,
            source_type=source_type,
            symbol=self.symbol,
            delay_ms=delay_ms,
            metadata=metadata or {},
        )
        
        if feature_timestamp not in self._records:
            self._records[feature_timestamp] = {}
        self._records[feature_timestamp][feature_name] = record
        
        if feature_name not in self._feature_index:
            self._feature_index[feature_name] = []
        if feature_timestamp not in self._feature_index[feature_name]:
            self._feature_index[feature_name].append(feature_timestamp)
        
        return record
    
    def store_features_batch(
        self,
        features: Dict[str, Any],
        feature_timestamp: int,
        available_at: Optional[int] = None,
        source_types: Optional[Dict[str, FeatureSourceType]] = None,
    ) -> Dict[str, PointInTimeFeatureRecord]:
        """批量存储特征"""
        records = {}
        source_types = source_types or {}
        
        for feature_name, value in features.items():
            source_type = source_types.get(feature_name, FeatureSourceType.INSTANT)
            record = self.store_feature(
                feature_name=feature_name,
                value=value,
                feature_timestamp=feature_timestamp,
                available_at=available_at,
                source_type=source_type,
            )
            if record:
                records[feature_name] = record
        
        return records
    
    def get_features_at_time(
        self,
        query_time: int,
        feature_names: Optional[List[str]] = None,
        include_blocked: bool = False,
    ) -> PointInTimeSnapshot:
        """
        获取指定时间点可用的特征
        
        Args:
            query_time: 查询时间戳
            feature_names: 指定特征列表（None表示所有）
            include_blocked: 是否包含被阻止的特征（用于调试）
        """
        available_features = {}
        feature_timestamps = {}
        available_at_times = {}
        blocked_features = []
        
        if feature_names is None:
            feature_names = list(self._feature_index.keys())
        
        for feature_name in feature_names:
            if feature_name in self.LABEL_FEATURES:
                blocked_features.append(f"{feature_name} (label - isolated)")
                continue
            
            timestamps = self._feature_index.get(feature_name, [])
            valid_timestamps = [ts for ts in timestamps if ts <= query_time]
            
            if not valid_timestamps:
                continue
            
            latest_ts = max(valid_timestamps)
            record = self._records.get(latest_ts, {}).get(feature_name)
            
            if record is None:
                continue
            
            check = self._get_guard().check_availability(
                feature_name=feature_name,
                feature_timestamp=record.feature_timestamp,
                replay_clock=query_time,
            )
            
            if check.status.value == "available":
                available_features[feature_name] = record.value
                feature_timestamps[feature_name] = record.feature_timestamp
                available_at_times[feature_name] = record.available_at
            else:
                blocked_features.append(feature_name)
                if self._log_access:
                    self._log_blocked_access(feature_name, query_time, record, check)
        
        snapshot = PointInTimeSnapshot(
            snapshot_timestamp=query_time,
            symbol=self.symbol,
            features=available_features,
            feature_timestamps=feature_timestamps,
            available_at_times=available_at_times,
            blocked_features=blocked_features,
        )
        
        if self._log_access:
            self._access_log.append({
                "query_time": query_time,
                "available_count": len(available_features),
                "blocked_count": len(blocked_features),
                "timestamp": datetime.utcnow().isoformat(),
            })
        
        return snapshot
    
    def get_label_at_time(
        self,
        query_time: int,
        label_name: str,
    ) -> Optional[Any]:
        """
        获取标签（仅用于训练，不能用于特征）
        
        这个方法应该只在训练数据生成时调用
        """
        if label_name not in self.LABEL_FEATURES:
            logger.warning(f"get_label_at_time called with non-label: {label_name}")
            return None
        
        labels = self._label_store.get(query_time, {})
        return labels.get(label_name)
    
    def get_feature_history(
        self,
        feature_name: str,
        start_time: int,
        end_time: int,
    ) -> pd.DataFrame:
        """获取特征历史"""
        timestamps = self._feature_index.get(feature_name, [])
        valid_timestamps = [ts for ts in timestamps if start_time <= ts <= end_time]
        
        records = []
        for ts in sorted(valid_timestamps):
            record = self._records.get(ts, {}).get(feature_name)
            if record:
                records.append({
                    "timestamp": ts,
                    "value": record.value,
                    "available_at": record.available_at,
                    "source_type": record.source_type.value,
                })
        
        if not records:
            return pd.DataFrame()
        
        return pd.DataFrame(records)
    
    def validate_no_leakage(
        self,
        start_time: int,
        end_time: int,
    ) -> Dict[str, Any]:
        """验证时间范围内没有数据泄漏"""
        issues = []
        
        for ts in sorted(self._records.keys()):
            if not (start_time <= ts <= end_time):
                continue
            
            for feature_name, record in self._records[ts].items():
                if record.available_at > ts:
                    issues.append({
                        "type": "feature_available_after_timestamp",
                        "feature": feature_name,
                        "timestamp": ts,
                        "available_at": record.available_at,
                        "delay_ms": record.delay_ms,
                    })
        
        return {
            "has_issues": len(issues) > 0,
            "issue_count": len(issues),
            "issues": issues[:100],
        }
    
    def _log_blocked_access(
        self,
        feature_name: str,
        query_time: int,
        record: PointInTimeFeatureRecord,
        check: Any,
    ):
        """记录被阻止的访问"""
        self._leakage_attempts.append({
            "feature_name": feature_name,
            "query_time": query_time,
            "feature_timestamp": record.feature_timestamp,
            "available_at": record.available_at,
            "status": check.status.value,
            "message": check.message,
            "timestamp": datetime.utcnow().isoformat(),
        })
    
    def get_leakage_report(self) -> Dict[str, Any]:
        """获取泄漏尝试报告"""
        feature_counts = {}
        for attempt in self._leakage_attempts:
            feature = attempt["feature_name"]
            feature_counts[feature] = feature_counts.get(feature, 0) + 1
        
        return {
            "total_attempts": len(self._leakage_attempts),
            "unique_features": len(feature_counts),
            "feature_counts": dict(sorted(
                feature_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:20]),
            "recent_attempts": self._leakage_attempts[-10:],
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_features = sum(len(features) for features in self._records.values())
        
        return {
            "symbol": self.symbol,
            "interval_ms": self.interval_ms,
            "total_timestamps": len(self._records),
            "total_feature_records": total_features,
            "unique_features": len(self._feature_index),
            "label_count": sum(len(labels) for labels in self._label_store.values()),
            "access_log_count": len(self._access_log),
            "leakage_attempts": len(self._leakage_attempts),
        }
    
    def clear(self):
        """清空存储"""
        self._records.clear()
        self._feature_index.clear()
        self._label_store.clear()
        self._access_log.clear()
        self._leakage_attempts.clear()
        logger.info(f"PointInTimeFeatureStore cleared for {self.symbol}")


_store_instances: Dict[str, PointInTimeFeatureStore] = {}


def get_point_in_time_store(
    symbol: str,
    interval_ms: int = 60000,
) -> PointInTimeFeatureStore:
    """获取 Point-In-Time Feature Store 实例"""
    key = f"{symbol}_{interval_ms}"
    if key not in _store_instances:
        _store_instances[key] = PointInTimeFeatureStore(symbol, interval_ms)
    return _store_instances[key]


def clear_all_stores():
    """清空所有存储实例"""
    for store in _store_instances.values():
        store.clear()
    _store_instances.clear()
