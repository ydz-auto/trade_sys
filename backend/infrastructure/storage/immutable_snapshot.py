"""
Immutable Feature Snapshot - 不可变特征快照

核心问题：
Feature Cache 可能被 overwrite，导致历史特征被污染。
如果特征生成逻辑改变，历史数据可能被错误更新。

解决方案：
1. 特征快照一旦创建就不可修改
2. 每个快照有唯一 ID 和版本号
3. 支持快照溯源和验证
4. 防止重生成污染
"""

from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
import copy

from infrastructure.logging import get_logger

logger = get_logger("storage.immutable_snapshot")


@dataclass(frozen=True)
class ImmutableFeatureSnapshot:
    """
    不可变特征快照
    
    使用 frozen=True 确保不可变性
    """
    snapshot_id: str
    snapshot_time: int
    symbol: str
    interval_ms: int
    version: int
    
    features: Dict[str, Any]
    feature_timestamps: Dict[str, int]
    available_at_times: Dict[str, int]
    
    source: str
    generation_hash: str
    
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def __post_init__(self):
        object.__setattr__(self, 'features', dict(self.features))
        object.__setattr__(self, 'feature_timestamps', dict(self.feature_timestamps))
        object.__setattr__(self, 'available_at_times', dict(self.available_at_times))
    
    def compute_hash(self) -> str:
        """计算快照哈希"""
        content = json.dumps({
            "snapshot_time": self.snapshot_time,
            "symbol": self.symbol,
            "features": self.features,
            "feature_timestamps": self.feature_timestamps,
        }, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()[:32]
    
    def verify_integrity(self) -> bool:
        """验证完整性"""
        computed_hash = self.compute_hash()
        return computed_hash == self.generation_hash
    
    def get_feature(self, name: str) -> Optional[Any]:
        """获取特征值"""
        return self.features.get(name)
    
    def get_feature_names(self) -> Set[str]:
        """获取所有特征名称"""
        return set(self.features.keys())
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "snapshot_id": self.snapshot_id,
            "snapshot_time": self.snapshot_time,
            "symbol": self.symbol,
            "interval_ms": self.interval_ms,
            "version": self.version,
            "features": dict(self.features),
            "feature_timestamps": dict(self.feature_timestamps),
            "available_at_times": dict(self.available_at_times),
            "source": self.source,
            "generation_hash": self.generation_hash,
            "created_at": self.created_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ImmutableFeatureSnapshot':
        """从字典创建"""
        return cls(
            snapshot_id=data["snapshot_id"],
            snapshot_time=data["snapshot_time"],
            symbol=data["symbol"],
            interval_ms=data["interval_ms"],
            version=data["version"],
            features=data["features"],
            feature_timestamps=data["feature_timestamps"],
            available_at_times=data["available_at_times"],
            source=data["source"],
            generation_hash=data["generation_hash"],
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
        )


class ImmutableSnapshotStore:
    """
    不可变快照存储
    
    核心功能：
    1. 创建不可变快照
    2. 按时间查询快照
    3. 验证快照完整性
    4. 防止快照被覆盖
    """
    
    def __init__(self, symbol: str, interval_ms: int = 60000):
        self.symbol = symbol
        self.interval_ms = interval_ms
        
        self._snapshots: Dict[str, ImmutableFeatureSnapshot] = {}
        self._time_index: Dict[int, str] = {}
        self._version_counter = 0
        
        self._access_log: List[Dict[str, Any]] = []
        self._modification_attempts: List[Dict[str, Any]] = []
    
    def create_snapshot(
        self,
        features: Dict[str, Any],
        snapshot_time: int,
        feature_timestamps: Optional[Dict[str, int]] = None,
        available_at_times: Optional[Dict[str, int]] = None,
        source: str = "unknown",
    ) -> ImmutableFeatureSnapshot:
        """
        创建不可变快照
        
        Args:
            features: 特征字典
            snapshot_time: 快照时间
            feature_timestamps: 特征时间戳
            available_at_times: 可用时间
            source: 来源
        
        Returns:
            ImmutableFeatureSnapshot: 创建的快照
        """
        self._version_counter += 1
        
        snapshot_id = f"snap_{self.symbol}_{snapshot_time}_{self._version_counter}"
        
        feature_timestamps = feature_timestamps or {k: snapshot_time for k in features.keys()}
        available_at_times = available_at_times or {k: snapshot_time for k in features.keys()}
        
        temp_snapshot = ImmutableFeatureSnapshot(
            snapshot_id=snapshot_id,
            snapshot_time=snapshot_time,
            symbol=self.symbol,
            interval_ms=self.interval_ms,
            version=self._version_counter,
            features=features,
            feature_timestamps=feature_timestamps,
            available_at_times=available_at_times,
            source=source,
            generation_hash="",
        )
        
        generation_hash = temp_snapshot.compute_hash()
        
        snapshot = ImmutableFeatureSnapshot(
            snapshot_id=snapshot_id,
            snapshot_time=snapshot_time,
            symbol=self.symbol,
            interval_ms=self.interval_ms,
            version=self._version_counter,
            features=features,
            feature_timestamps=feature_timestamps,
            available_at_times=available_at_times,
            source=source,
            generation_hash=generation_hash,
        )
        
        if snapshot_time in self._time_index:
            existing_id = self._time_index[snapshot_time]
            self._log_modification_attempt(existing_id, snapshot_id, snapshot_time)
            logger.warning(
                f"Snapshot already exists at {snapshot_time}, "
                f"existing_id={existing_id}, new_id={snapshot_id}. "
                f"Keeping existing snapshot (immutable)."
            )
            return self._snapshots[existing_id]
        
        self._snapshots[snapshot_id] = snapshot
        self._time_index[snapshot_time] = snapshot_id
        
        logger.debug(f"Created immutable snapshot: {snapshot_id}")
        
        return snapshot
    
    def get_snapshot(self, snapshot_id: str) -> Optional[ImmutableFeatureSnapshot]:
        """获取快照"""
        snapshot = self._snapshots.get(snapshot_id)
        
        if snapshot:
            self._access_log.append({
                "action": "get",
                "snapshot_id": snapshot_id,
                "timestamp": datetime.utcnow().isoformat(),
            })
        
        return snapshot
    
    def get_snapshot_at_time(self, query_time: int) -> Optional[ImmutableFeatureSnapshot]:
        """获取指定时间点的快照"""
        valid_times = [t for t in self._time_index.keys() if t <= query_time]
        
        if not valid_times:
            return None
        
        closest_time = max(valid_times)
        snapshot_id = self._time_index[closest_time]
        
        return self._snapshots.get(snapshot_id)
    
    def get_latest_snapshot(self) -> Optional[ImmutableFeatureSnapshot]:
        """获取最新快照"""
        if not self._time_index:
            return None
        
        latest_time = max(self._time_index.keys())
        snapshot_id = self._time_index[latest_time]
        
        return self._snapshots.get(snapshot_id)
    
    def verify_snapshot(self, snapshot_id: str) -> Dict[str, Any]:
        """验证快照完整性"""
        snapshot = self._snapshots.get(snapshot_id)
        
        if snapshot is None:
            return {
                "valid": False,
                "error": "Snapshot not found",
            }
        
        is_valid = snapshot.verify_integrity()
        
        return {
            "valid": is_valid,
            "snapshot_id": snapshot_id,
            "snapshot_time": snapshot.snapshot_time,
            "version": snapshot.version,
            "computed_hash": snapshot.compute_hash(),
            "stored_hash": snapshot.generation_hash,
        }
    
    def verify_all_snapshots(self) -> Dict[str, Any]:
        """验证所有快照"""
        results = {
            "total": len(self._snapshots),
            "valid": 0,
            "invalid": 0,
            "details": [],
        }
        
        for snapshot_id in self._snapshots.keys():
            verification = self.verify_snapshot(snapshot_id)
            
            if verification["valid"]:
                results["valid"] += 1
            else:
                results["invalid"] += 1
                results["details"].append(verification)
        
        return results
    
    def get_snapshots_in_range(
        self,
        start_time: int,
        end_time: int,
    ) -> List[ImmutableFeatureSnapshot]:
        """获取时间范围内的快照"""
        snapshots = []
        
        for time, snapshot_id in self._time_index.items():
            if start_time <= time <= end_time:
                snapshot = self._snapshots.get(snapshot_id)
                if snapshot:
                    snapshots.append(snapshot)
        
        return sorted(snapshots, key=lambda s: s.snapshot_time)
    
    def _log_modification_attempt(
        self,
        existing_id: str,
        new_id: str,
        snapshot_time: int,
    ):
        """记录修改尝试"""
        self._modification_attempts.append({
            "existing_id": existing_id,
            "new_id": new_id,
            "snapshot_time": snapshot_time,
            "timestamp": datetime.utcnow().isoformat(),
        })
    
    def get_modification_report(self) -> Dict[str, Any]:
        """获取修改尝试报告"""
        return {
            "total_attempts": len(self._modification_attempts),
            "attempts": self._modification_attempts[-20:],
        }
    
    def reset(self):
        """重置存储状态（用于新 session）"""
        self._snapshots.clear()
        self._time_index.clear()
        self._version_counter = 0
        self._access_log.clear()
        self._modification_attempts.clear()
        logger.info(f"ImmutableSnapshotStore reset for {self.symbol}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "symbol": self.symbol,
            "interval_ms": self.interval_ms,
            "total_snapshots": len(self._snapshots),
            "version_counter": self._version_counter,
            "modification_attempts": len(self._modification_attempts),
            "earliest_snapshot": min(self._time_index.keys()) if self._time_index else None,
            "latest_snapshot": max(self._time_index.keys()) if self._time_index else None,
        }
    
    def export_snapshots(self) -> List[Dict[str, Any]]:
        """导出所有快照"""
        return [s.to_dict() for s in sorted(
            self._snapshots.values(),
            key=lambda s: s.snapshot_time
        )]
    
    def import_snapshots(self, snapshots: List[Dict[str, Any]]) -> int:
        """导入快照"""
        imported = 0
        
        for data in snapshots:
            try:
                snapshot = ImmutableFeatureSnapshot.from_dict(data)
                
                if snapshot.snapshot_time not in self._time_index:
                    self._snapshots[snapshot.snapshot_id] = snapshot
                    self._time_index[snapshot.snapshot_time] = snapshot.snapshot_id
                    
                    if snapshot.version > self._version_counter:
                        self._version_counter = snapshot.version
                    
                    imported += 1
            
            except Exception as e:
                logger.warning(f"Failed to import snapshot: {e}")
        
        return imported


_store_instances: Dict[str, ImmutableSnapshotStore] = {}


def get_immutable_snapshot_store(
    symbol: str,
    interval_ms: int = 60000,
) -> ImmutableSnapshotStore:
    """获取不可变快照存储实例"""
    key = f"{symbol}_{interval_ms}"
    if key not in _store_instances:
        _store_instances[key] = ImmutableSnapshotStore(symbol, interval_ms)
    return _store_instances[key]


def create_immutable_snapshot(
    symbol: str,
    features: Dict[str, Any],
    snapshot_time: int,
    **kwargs,
) -> ImmutableFeatureSnapshot:
    """创建不可变快照的便捷函数"""
    store = get_immutable_snapshot_store(symbol)
    return store.create_snapshot(features, snapshot_time, **kwargs)
