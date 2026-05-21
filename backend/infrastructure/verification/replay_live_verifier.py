"""
Replay-Live Consistency Verifier - Replay vs Live 一致性验证器

核心问题：
如何确保 Replay 和 Live 在相同时间产生相同的特征和决策？

解决方案：
1. 同时运行 Replay 和 Live（或保存的历史 Live）
2. 在相同时间点对比特征向量
3. 生成详细的一致性报告
4. 可视化差异
"""

from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import numpy as np
import pandas as pd
import json

from infrastructure.logging import get_logger
from infrastructure.runtime_clock import RuntimeClock, ClockMode
from infrastructure.storage.immutable_snapshot import ImmutableFeatureSnapshot
from infrastructure.event.unified_schema import UnifiedEvent

logger = get_logger("infrastructure.consistency_verifier")


class ConsistencyLevel(Enum):
    """一致性级别"""
    EXACT = "exact"  # 完全一致（浮点数精确相等）
    TIGHT = "tight"  # 1e-8 容差
    NORMAL = "normal"  # 1e-6 容差
    LOOSE = "loose"  # 1e-3 容差
    NONE = "none"  # 完全不一致


@dataclass
class FeatureComparison:
    """单个特征对比结果"""
    feature_name: str
    replay_value: Any
    live_value: Any
    
    is_equal: bool
    absolute_diff: float
    relative_diff: float
    
    level: ConsistencyLevel
    issue: Optional[str] = None


@dataclass
class TimePointComparison:
    """时间点对比结果"""
    timestamp: int
    
    feature_comparisons: List[FeatureComparison]
    
    total_features: int = 0
    consistent_features: int = 0
    inconsistent_features: int = 0
    
    max_absolute_diff: float = 0.0
    avg_absolute_diff: float = 0.0
    
    is_consistent: bool = True
    summary: str = ""
    
    def __post_init__(self):
        """计算统计"""
        self.total_features = len(self.feature_comparisons)
        self.consistent_features = sum(1 for c in self.feature_comparisons if c.is_equal)
        self.inconsistent_features = self.total_features - self.consistent_features
        
        diffs = [c.absolute_diff for c in self.feature_comparisons]
        if diffs:
            self.max_absolute_diff = float(max(diffs))
            self.avg_absolute_diff = float(np.mean(diffs))
        
        self.is_consistent = self.consistent_features == self.total_features
        
        if self.is_consistent:
            self.summary = "All features consistent"
        else:
            inconsistent = [c.feature_name for c in self.feature_comparisons if not c.is_equal]
            self.summary = f"Inconsistent: {', '.join(inconsistent[:5])}"


@dataclass
class ConsistencyReport:
    """完整一致性报告"""
    symbol: str
    start_timestamp: int
    end_timestamp: int
    
    time_point_comparisons: List[TimePointComparison]
    
    total_time_points: int = 0
    consistent_time_points: int = 0
    inconsistent_time_points: int = 0
    
    overall_max_diff: float = 0.0
    overall_avg_diff: float = 0.0
    
    inconsistent_features: Dict[str, int] = field(default_factory=dict)
    
    report_timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def __post_init__(self):
        """计算统计"""
        self.total_time_points = len(self.time_point_comparisons)
        self.consistent_time_points = sum(1 for c in self.time_point_comparisons if c.is_consistent)
        self.inconsistent_time_points = self.total_time_points - self.consistent_time_points
        
        all_diffs = []
        for tp in self.time_point_comparisons:
            all_diffs.extend([c.absolute_diff for c in tp.feature_comparisons])
            
            for c in tp.feature_comparisons:
                if not c.is_equal:
                    self.inconsistent_features[c.feature_name] = \
                        self.inconsistent_features.get(c.feature_name, 0) + 1
        
        if all_diffs:
            self.overall_max_diff = float(max(all_diffs))
            self.overall_avg_diff = float(np.mean(all_diffs))
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "symbol": self.symbol,
            "start_timestamp": self.start_timestamp,
            "end_timestamp": self.end_timestamp,
            "total_time_points": self.total_time_points,
            "consistent_time_points": self.consistent_time_points,
            "inconsistent_time_points": self.inconsistent_time_points,
            "overall_max_diff": self.overall_max_diff,
            "overall_avg_diff": self.overall_avg_diff,
            "inconsistent_features": dict(sorted(
                self.inconsistent_features.items(),
                key=lambda x: x[1], reverse=True
            )),
            "report_timestamp": self.report_timestamp
        }
    
    def save(self, file_path: str):
        """保存报告"""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2)


class ReplayLiveConsistencyVerifier:
    """
    Replay vs Live 一致性验证器
    
    使用方法：
    1. 同时记录 Replay 和 Live 产生的特征
    2. 使用相同的输入
    3. 在相同时间点对比
    4. 生成一致性报告
    """
    
    def __init__(self, symbol: str):
        self.symbol = symbol
        
        self.replay_snapshots: Dict[int, ImmutableFeatureSnapshot] = {}
        self.live_snapshots: Dict[int, ImmutableFeatureSnapshot] = {}
        
        self.comparisons: List[TimePointComparison] = []
    
    def record_replay(self, timestamp: int, snapshot: ImmutableFeatureSnapshot):
        """记录 Replay 快照"""
        self.replay_snapshots[timestamp] = snapshot
    
    def record_live(self, timestamp: int, snapshot: ImmutableFeatureSnapshot):
        """记录 Live 快照"""
        self.live_snapshots[timestamp] = snapshot
    
    def compare_features(
        self,
        replay_feature: Any,
        live_feature: Any,
        feature_name: str,
        tolerance: float = 1e-6,
        relative_tolerance: float = 1e-4
    ) -> FeatureComparison:
        """
        比较单个特征
        """
        # 处理 NaN/None
        if replay_feature is None and live_feature is None:
            return FeatureComparison(
                feature_name=feature_name,
                replay_value=None,
                live_value=None,
                is_equal=True,
                absolute_diff=0.0,
                relative_diff=0.0,
                level=ConsistencyLevel.EXACT
            )
        
        if (replay_feature is None) != (live_feature is None):
            return FeatureComparison(
                feature_name=feature_name,
                replay_value=replay_feature,
                live_value=live_feature,
                is_equal=False,
                absolute_diff=float('inf'),
                relative_diff=float('inf'),
                level=ConsistencyLevel.NONE,
                issue="One is None/NaN"
            )
        
        # 处理 NaN
        if np.isnan(replay_feature) and np.isnan(live_feature):
            return FeatureComparison(
                feature_name=feature_name,
                replay_value=replay_feature,
                live_value=live_feature,
                is_equal=True,
                absolute_diff=0.0,
                relative_diff=0.0,
                level=ConsistencyLevel.EXACT
            )
        
        if np.isnan(replay_feature) or np.isnan(live_feature):
            return FeatureComparison(
                feature_name=feature_name,
                replay_value=replay_feature,
                live_value=live_feature,
                is_equal=False,
                absolute_diff=float('inf'),
                relative_diff=float('inf'),
                level=ConsistencyLevel.NONE,
                issue="One is NaN"
            )
        
        # 数值比较
        abs_diff = abs(float(replay_feature) - float(live_feature))
        
        max_val = max(abs(float(replay_feature)), abs(float(live_feature)), 1e-10)
        rel_diff = abs_diff / max_val
        
        # 确定一致性级别
        if abs_diff < 1e-12:
            level = ConsistencyLevel.EXACT
        elif abs_diff < 1e-8:
            level = ConsistencyLevel.TIGHT
        elif abs_diff < tolerance:
            level = ConsistencyLevel.NORMAL
        elif abs_diff < 1e-3:
            level = ConsistencyLevel.LOOSE
        else:
            level = ConsistencyLevel.NONE
        
        is_equal = level != ConsistencyLevel.NONE
        
        return FeatureComparison(
            feature_name=feature_name,
            replay_value=replay_feature,
            live_value=live_feature,
            is_equal=is_equal,
            absolute_diff=abs_diff,
            relative_diff=rel_diff,
            level=level
        )
    
    def compare_time_point(
        self,
        timestamp: int,
        replay_snapshot: ImmutableFeatureSnapshot,
        live_snapshot: ImmutableFeatureSnapshot,
        tolerance: float = 1e-6
    ) -> TimePointComparison:
        """比较单个时间点"""
        comparisons: List[FeatureComparison] = []
        
        # 合并特征名
        all_features = set(replay_snapshot.features.keys()).union(
            set(live_snapshot.features.keys())
        )
        
        for feature_name in all_features:
            replay_val = replay_snapshot.features.get(feature_name)
            live_val = live_snapshot.features.get(feature_name)
            
            comp = self.compare_features(replay_val, live_val, feature_name, tolerance)
            comparisons.append(comp)
        
        return TimePointComparison(
            timestamp=timestamp,
            feature_comparisons=comparisons
        )
    
    def run_verification(
        self,
        tolerance: float = 1e-6,
        common_timestamps_only: bool = True
    ) -> ConsistencyReport:
        """运行完整验证"""
        self.comparisons = []
        
        # 确定对比的时间点
        replay_timestamps = set(self.replay_snapshots.keys())
        live_timestamps = set(self.live_snapshots.keys())
        
        if common_timestamps_only:
            timestamps = sorted(replay_timestamps.intersection(live_timestamps))
        else:
            timestamps = sorted(replay_timestamps.union(live_timestamps))
        
        if not timestamps:
            logger.warning("No common timestamps to compare")
            return ConsistencyReport(
                symbol=self.symbol,
                start_timestamp=0,
                end_timestamp=0,
                time_point_comparisons=[]
            )
        
        # 逐个时间点对比
        for ts in timestamps:
            replay_snap = self.replay_snapshots.get(ts)
            live_snap = self.live_snapshots.get(ts)
            
            if replay_snap and live_snap:
                comp = self.compare_time_point(ts, replay_snap, live_snap, tolerance)
                self.comparisons.append(comp)
        
        return ConsistencyReport(
            symbol=self.symbol,
            start_timestamp=timestamps[0] if timestamps else 0,
            end_timestamp=timestamps[-1] if timestamps else 0,
            time_point_comparisons=self.comparisons
        )
    
    def get_summary(self) -> Dict[str, Any]:
        """获取总结"""
        if not self.comparisons:
            return {"status": "No comparisons"}
        
        report = self.run_verification()
        return report.to_dict()


# 便捷函数
def create_consistency_verifier(symbol: str) -> ReplayLiveConsistencyVerifier:
    """创建验证器"""
    return ReplayLiveConsistencyVerifier(symbol)


def verify_replay_live_consistency(
    symbol: str,
    replay_snapshots: Dict[int, ImmutableFeatureSnapshot],
    live_snapshots: Dict[int, ImmutableFeatureSnapshot],
    tolerance: float = 1e-6
) -> ConsistencyReport:
    """便捷函数：运行验证"""
    verifier = create_consistency_verifier(symbol)
    
    for ts, snap in replay_snapshots.items():
        verifier.record_replay(ts, snap)
    
    for ts, snap in live_snapshots.items():
        verifier.record_live(ts, snap)
    
    return verifier.run_verification(tolerance)
