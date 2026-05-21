"""
Live vs Replay Feature Consistency Test - Live vs Replay 特征一致性测试

核心功能：
验证同一时间点，Live Runtime 和 Replay Runtime 生成的特征向量完全一致。

测试原理：
1. 在时间 T，Live Runtime 生成特征向量 F_live
2. 在时间 T，Replay Runtime 生成特征向量 F_replay
3. 比较 F_live 和 F_replay，应该 bit-level 接近一致

这是专业量化系统的核心要求。
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
import numpy as np
import pandas as pd

from infrastructure.logging import get_logger
from infrastructure.verification.determinism import (
    DeterminismVerifier,
    VerificationResult,
    VerificationStatus,
)
from infrastructure.storage.point_in_time_store import (
    PointInTimeFeatureStore,
    get_point_in_time_store,
)
from shared.replay.feature_availability_guard import (
    FeatureAvailabilityGuard,
    get_feature_availability_guard,
)

logger = get_logger("verification.live_replay_consistency")


@dataclass
class FeatureComparisonResult:
    """特征比较结果"""
    timestamp: int
    symbol: str
    
    live_features: Dict[str, Any]
    replay_features: Dict[str, Any]
    
    matching_features: List[str]
    mismatching_features: List[str]
    missing_in_live: List[str]
    missing_in_replay: List[str]
    
    max_difference: float
    mean_difference: float
    
    is_consistent: bool
    tolerance: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "matching_count": len(self.matching_features),
            "mismatching_count": len(self.mismatching_features),
            "missing_in_live_count": len(self.missing_in_live),
            "missing_in_replay_count": len(self.missing_in_replay),
            "max_difference": self.max_difference,
            "mean_difference": self.mean_difference,
            "is_consistent": self.is_consistent,
            "tolerance": self.tolerance,
        }


@dataclass
class ConsistencyTestConfig:
    """一致性测试配置"""
    symbol: str = "BTCUSDT"
    interval_ms: int = 60000
    
    tolerance: float = 1e-6
    relative_tolerance: float = 1e-4
    
    test_timestamps: List[int] = field(default_factory=list)
    
    feature_whitelist: Optional[List[str]] = None
    feature_blacklist: List[str] = field(default_factory=lambda: [
        "timestamp", "datetime", "symbol", "exchange"
    ])
    
    strict_mode: bool = True
    log_details: bool = True


class LiveReplayConsistencyVerifier:
    """
    Live vs Replay 一致性验证器
    
    验证同一时间点，Live 和 Replay 生成的特征是否一致
    """
    
    def __init__(self, config: Optional[ConsistencyTestConfig] = None):
        self.config = config or ConsistencyTestConfig()
        self.guard = get_feature_availability_guard(self.config.interval_ms)
        
        self._comparison_results: List[FeatureComparisonResult] = []
        self._consistency_issues: List[Dict[str, Any]] = []
    
    async def verify_consistency(
        self,
        live_store: PointInTimeFeatureStore,
        replay_store: PointInTimeFeatureStore,
        timestamp: int,
    ) -> FeatureComparisonResult:
        """
        验证指定时间点的特征一致性
        
        Args:
            live_store: Live Runtime 的特征存储
            replay_store: Replay Runtime 的特征存储
            timestamp: 验证时间点
        """
        live_snapshot = live_store.get_features_at_time(timestamp)
        replay_snapshot = replay_store.get_features_at_time(timestamp)
        
        live_features = live_snapshot.features
        replay_features = replay_snapshot.features
        
        matching = []
        mismatching = []
        missing_in_live = []
        missing_in_replay = []
        
        all_feature_names = set(live_features.keys()) | set(replay_features.keys())
        
        for name in all_feature_names:
            if name in self.config.feature_blacklist:
                continue
            
            if self.config.feature_whitelist and name not in self.config.feature_whitelist:
                continue
            
            if name not in live_features:
                missing_in_live.append(name)
                continue
            
            if name not in replay_features:
                missing_in_replay.append(name)
                continue
            
            live_val = live_features[name]
            replay_val = replay_features[name]
            
            if self._compare_values(live_val, replay_val):
                matching.append(name)
            else:
                mismatching.append(name)
        
        max_diff, mean_diff = self._compute_differences(
            live_features, replay_features, matching + mismatching
        )
        
        is_consistent = (
            len(mismatching) == 0 and
            len(missing_in_live) == 0 and
            len(missing_in_replay) == 0
        )
        
        result = FeatureComparisonResult(
            timestamp=timestamp,
            symbol=self.config.symbol,
            live_features=live_features,
            replay_features=replay_features,
            matching_features=matching,
            mismatching_features=mismatching,
            missing_in_live=missing_in_live,
            missing_in_replay=missing_in_replay,
            max_difference=max_diff,
            mean_difference=mean_diff,
            is_consistent=is_consistent,
            tolerance=self.config.tolerance,
        )
        
        self._comparison_results.append(result)
        
        if not is_consistent:
            self._consistency_issues.append({
                "timestamp": timestamp,
                "mismatching": mismatching[:10],
                "missing_in_live": missing_in_live[:10],
                "missing_in_replay": missing_in_replay[:10],
                "max_difference": max_diff,
            })
            
            if self.config.strict_mode:
                logger.error(
                    f"Feature inconsistency at {timestamp}: "
                    f"{len(mismatching)} mismatching, "
                    f"{len(missing_in_live)} missing in live, "
                    f"{len(missing_in_replay)} missing in replay"
                )
        
        return result
    
    def _compare_values(self, v1: Any, v2: Any) -> bool:
        """比较两个值是否相等"""
        if v1 is None and v2 is None:
            return True
        if v1 is None or v2 is None:
            return False
        
        if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
            if np.isnan(v1) and np.isnan(v2):
                return True
            if np.isnan(v1) or np.isnan(v2):
                return False
            
            abs_diff = abs(v1 - v2)
            if abs_diff <= self.config.tolerance:
                return True
            
            if self.config.relative_tolerance > 0:
                max_val = max(abs(v1), abs(v2))
                if max_val > 0:
                    rel_diff = abs_diff / max_val
                    return rel_diff <= self.config.relative_tolerance
            
            return False
        
        return v1 == v2
    
    def _compute_differences(
        self,
        live_features: Dict[str, Any],
        replay_features: Dict[str, Any],
        feature_names: List[str],
    ) -> Tuple[float, float]:
        """计算特征差异"""
        differences = []
        
        for name in feature_names:
            if name not in live_features or name not in replay_features:
                continue
            
            v1 = live_features[name]
            v2 = replay_features[name]
            
            if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
                if not np.isnan(v1) and not np.isnan(v2):
                    differences.append(abs(v1 - v2))
        
        if not differences:
            return 0.0, 0.0
        
        return max(differences), sum(differences) / len(differences)
    
    async def verify_multiple_timestamps(
        self,
        live_store: PointInTimeFeatureStore,
        replay_store: PointInTimeFeatureStore,
        timestamps: List[int],
    ) -> Dict[str, Any]:
        """验证多个时间点的一致性"""
        results = []
        
        for ts in timestamps:
            result = await self.verify_consistency(live_store, replay_store, ts)
            results.append(result)
        
        total = len(results)
        consistent = sum(1 for r in results if r.is_consistent)
        
        all_matching = set()
        all_mismatching = set()
        for r in results:
            all_matching.update(r.matching_features)
            all_mismatching.update(r.mismatching_features)
        
        return {
            "total_timestamps": total,
            "consistent_timestamps": consistent,
            "consistency_rate": consistent / total if total > 0 else 0,
            "total_matching_features": len(all_matching),
            "total_mismatching_features": len(all_mismatching),
            "results": [r.to_dict() for r in results],
            "issues": self._consistency_issues,
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """获取验证摘要"""
        total = len(self._comparison_results)
        consistent = sum(1 for r in self._comparison_results if r.is_consistent)
        
        return {
            "total_comparisons": total,
            "consistent_comparisons": consistent,
            "consistency_rate": consistent / total if total > 0 else 0,
            "issues_count": len(self._consistency_issues),
            "config": {
                "symbol": self.config.symbol,
                "tolerance": self.config.tolerance,
                "relative_tolerance": self.config.relative_tolerance,
            },
        }


class MockLiveRuntime:
    """模拟 Live Runtime"""
    
    def __init__(self, symbol: str, interval_ms: int = 60000):
        self.symbol = symbol
        self.interval_ms = interval_ms
        self.store = get_point_in_time_store(symbol, interval_ms)
        self.guard = get_feature_availability_guard(interval_ms)
    
    async def generate_features(self, timestamp: int) -> Dict[str, Any]:
        """生成特征（模拟 Live 场景）"""
        features = {
            "spread": np.random.uniform(0.01, 0.05),
            "trade_delta": np.random.uniform(-100, 100),
            "aggressive_buy_ratio": np.random.uniform(0.3, 0.7),
            "volume": np.random.uniform(1000, 10000),
        }
        
        self.store.store_features_batch(features, timestamp)
        
        return features


class MockReplayRuntime:
    """模拟 Replay Runtime"""
    
    def __init__(self, symbol: str, interval_ms: int = 60000):
        self.symbol = symbol
        self.interval_ms = interval_ms
        self.store = get_point_in_time_store(symbol, interval_ms)
        self.guard = get_feature_availability_guard(interval_ms)
        self._current_time = 0
    
    def set_time(self, timestamp: int):
        """设置当前回放时间"""
        self._current_time = timestamp
    
    async def generate_features(self, timestamp: int) -> Dict[str, Any]:
        """生成特征（模拟 Replay 场景）"""
        self.set_time(timestamp)
        
        features = {
            "spread": np.random.uniform(0.01, 0.05),
            "trade_delta": np.random.uniform(-100, 100),
            "aggressive_buy_ratio": np.random.uniform(0.3, 0.7),
            "volume": np.random.uniform(1000, 10000),
        }
        
        self.store.store_features_batch(features, timestamp)
        
        return features


class TestLiveReplayConsistency:
    """Live vs Replay 一致性测试"""
    
    @pytest.fixture
    def verifier(self):
        """验证器 fixture"""
        config = ConsistencyTestConfig(
            symbol="BTCUSDT",
            tolerance=1e-6,
        )
        return LiveReplayConsistencyVerifier(config)
    
    @pytest.fixture
    def live_runtime(self):
        """Live Runtime fixture"""
        return MockLiveRuntime("BTCUSDT")
    
    @pytest.fixture
    def replay_runtime(self):
        """Replay Runtime fixture"""
        return MockReplayRuntime("BTCUSDT")
    
    @pytest.mark.asyncio
    async def test_single_timestamp_consistency(self, verifier, live_runtime, replay_runtime):
        """测试单个时间点的一致性"""
        timestamp = int(datetime(2024, 1, 1, 10, 15, 0).timestamp() * 1000)
        
        np.random.seed(42)
        await live_runtime.generate_features(timestamp)
        
        np.random.seed(42)
        await replay_runtime.generate_features(timestamp)
        
        result = await verifier.verify_consistency(
            live_runtime.store,
            replay_runtime.store,
            timestamp,
        )
        
        assert result.is_consistent, f"Features not consistent: {result.mismatching_features}"
    
    @pytest.mark.asyncio
    async def test_multiple_timestamps_consistency(self, verifier, live_runtime, replay_runtime):
        """测试多个时间点的一致性"""
        base_time = datetime(2024, 1, 1, 10, 0, 0)
        timestamps = [
            int((base_time + timedelta(minutes=i)).timestamp() * 1000)
            for i in range(10)
        ]
        
        for ts in timestamps:
            np.random.seed(ts % 10000)
            await live_runtime.generate_features(ts)
            
            np.random.seed(ts % 10000)
            await replay_runtime.generate_features(ts)
        
        results = await verifier.verify_multiple_timestamps(
            live_runtime.store,
            replay_runtime.store,
            timestamps,
        )
        
        assert results["consistency_rate"] == 1.0, f"Consistency rate: {results['consistency_rate']}"
    
    @pytest.mark.asyncio
    async def test_feature_availability_guard(self, verifier):
        """测试特征可用性守卫"""
        guard = get_feature_availability_guard()
        
        check = guard.check_availability(
            feature_name="volatility_1h",
            feature_timestamp=int(datetime(2024, 1, 1, 10, 0, 0).timestamp() * 1000),
            replay_clock=int(datetime(2024, 1, 1, 10, 15, 0).timestamp() * 1000),
        )
        
        assert check.status == FeatureAvailabilityStatus.NOT_YET_AVAILABLE
    
    @pytest.mark.asyncio
    async def test_point_in_time_store_label_isolation(self):
        """测试 Point-In-Time Store 的 Label 隔离"""
        store = get_point_in_time_store("BTCUSDT")
        
        store.store_feature("future_return_1h", 0.05, 1704110400000)
        store.store_feature("spread", 0.02, 1704110400000)
        
        snapshot = store.get_features_at_time(1704110400000)
        
        assert "spread" in snapshot.features
        assert "future_return_1h" not in snapshot.features
        assert "future_return_1h (label - isolated)" in snapshot.blocked_features
    
    def test_verifier_summary(self, verifier):
        """测试验证器摘要"""
        summary = verifier.get_summary()
        
        assert "total_comparisons" in summary
        assert "consistency_rate" in summary


async def run_consistency_test(
    symbol: str = "BTCUSDT",
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    interval_minutes: int = 5,
) -> Dict[str, Any]:
    """
    运行一致性测试
    
    Args:
        symbol: 交易对
        start_time: 开始时间
        end_time: 结束时间
        interval_minutes: 时间间隔（分钟）
    """
    if start_time is None:
        start_time = datetime(2024, 1, 1, 0, 0, 0)
    if end_time is None:
        end_time = start_time + timedelta(hours=1)
    
    config = ConsistencyTestConfig(symbol=symbol)
    verifier = LiveReplayConsistencyVerifier(config)
    
    live_runtime = MockLiveRuntime(symbol)
    replay_runtime = MockReplayRuntime(symbol)
    
    timestamps = []
    current = start_time
    while current <= end_time:
        timestamps.append(int(current.timestamp() * 1000))
        current += timedelta(minutes=interval_minutes)
    
    results = await verifier.verify_multiple_timestamps(
        live_runtime.store,
        replay_runtime.store,
        timestamps,
    )
    
    return results


if __name__ == "__main__":
    result = asyncio.run(run_consistency_test())
    print(f"Consistency test result: {result['consistency_rate']:.2%}")
