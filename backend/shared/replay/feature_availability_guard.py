"""
Feature Availability Guard - 特征可用性守卫

核心功能：
1. 确保在回放时只使用当前时间点可用的特征
2. 防止多周期聚合特征的未来泄漏
3. 记录特征的时间纪律信息

使用场景：
- Replay Runtime 回放时检查特征可用性
- 回测系统验证特征时间因果关系
- 实时系统确保特征延迟正确
"""

from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import pandas as pd

from infrastructure.logging import get_logger

logger = get_logger("feature_availability_guard")


class FeatureAvailabilityStatus(Enum):
    """特征可用性状态"""
    AVAILABLE = "available"
    NOT_YET_AVAILABLE = "not_yet_available"
    FUTURE_DERIVED = "future_derived"
    UNKNOWN = "unknown"


@dataclass
class FeatureAvailabilityRule:
    """特征可用性规则"""
    feature_name: str
    source_time: int
    available_at: int
    delay_ms: int
    category: str
    requires_closed_candle: bool = False
    aggregation_period_ms: Optional[int] = None


@dataclass
class FeatureAvailabilityCheck:
    """特征可用性检查结果"""
    feature_name: str
    status: FeatureAvailabilityStatus
    replay_clock: int
    source_time: int
    available_at: int
    delay_ms: int
    message: str = ""


class FeatureAvailabilityGuard:
    """
    特征可用性守卫
    
    核心原则：
    1. 当前K线只能使用已关闭的历史K线数据
    2. 多周期聚合特征必须等待周期结束
    3. ZScore等统计特征必须使用rolling window
    """
    
    DEFAULT_INTERVAL_MS = 60000
    
    MULTI_PERIOD_FEATURES = {
        "volatility_5m": {"period_ms": 5 * 60 * 1000, "delay_periods": 1},
        "volatility_15m": {"period_ms": 15 * 60 * 1000, "delay_periods": 1},
        "volatility_1h": {"period_ms": 60 * 60 * 1000, "delay_periods": 1},
        "volatility_4h": {"period_ms": 4 * 60 * 60 * 1000, "delay_periods": 1},
        "trend_5m": {"period_ms": 5 * 60 * 1000, "delay_periods": 1},
        "trend_15m": {"period_ms": 15 * 60 * 1000, "delay_periods": 1},
        "trend_1h": {"period_ms": 60 * 60 * 1000, "delay_periods": 1},
    }
    
    DERIVATIVES_FEATURES = {
        "funding_zscore": {"delay_periods": 1, "lookback": 240},
        "oi_zscore": {"delay_periods": 1, "lookback": 240},
        "leverage_crowdedness": {"delay_periods": 1, "lookback": 240},
    }
    
    LIQUIDATION_FEATURES = {
        "chain_probability": {"delay_periods": 1, "lookback": 30},
        "panic_score": {"delay_periods": 1, "lookback": 10},
        "reversal_probability": {"delay_periods": 1, "lookback": 30},
    }
    
    REGIME_FEATURES = {
        "volatility_regime": {"delay_periods": 1, "lookback": 60},
        "trend_regime": {"delay_periods": 1, "lookback": 20},
        "liquidity_regime": {"delay_periods": 1, "lookback": 30},
        "leverage_regime": {"delay_periods": 1, "lookback": 60},
    }
    
    SAFE_INSTANT_FEATURES = {
        "spread", "imbalance_5", "trade_delta", "aggressive_buy_ratio",
        "sweep_score", "oi_delta", "funding_rate", "liquidation_cluster",
        "news_sentiment", "twitter_velocity"
    }
    
    def __init__(self, interval_ms: int = 60000):
        self.interval_ms = interval_ms
        self._rules: Dict[str, FeatureAvailabilityRule] = {}
        self._build_rules()
    
    def _build_rules(self):
        """构建特征可用性规则"""
        for feature, config in self.MULTI_PERIOD_FEATURES.items():
            period_ms = config["period_ms"]
            delay_periods = config["delay_periods"]
            self._rules[feature] = FeatureAvailabilityRule(
                feature_name=feature,
                source_time=0,
                available_at=period_ms,
                delay_ms=period_ms * delay_periods,
                category="multi_period",
                requires_closed_candle=True,
                aggregation_period_ms=period_ms
            )
        
        for feature, config in self.DERIVATIVES_FEATURES.items():
            self._rules[feature] = FeatureAvailabilityRule(
                feature_name=feature,
                source_time=0,
                available_at=self.interval_ms,
                delay_ms=self.interval_ms * config["delay_periods"],
                category="derivatives"
            )
        
        for feature, config in self.LIQUIDATION_FEATURES.items():
            self._rules[feature] = FeatureAvailabilityRule(
                feature_name=feature,
                source_time=0,
                available_at=self.interval_ms,
                delay_ms=self.interval_ms * config["delay_periods"],
                category="liquidation"
            )
        
        for feature, config in self.REGIME_FEATURES.items():
            self._rules[feature] = FeatureAvailabilityRule(
                feature_name=feature,
                source_time=0,
                available_at=self.interval_ms,
                delay_ms=self.interval_ms * config["delay_periods"],
                category="regime"
            )
        
        for feature in self.SAFE_INSTANT_FEATURES:
            self._rules[feature] = FeatureAvailabilityRule(
                feature_name=feature,
                source_time=0,
                available_at=0,
                delay_ms=0,
                category="instant"
            )
    
    def check_availability(
        self,
        feature_name: str,
        feature_timestamp: int,
        replay_clock: int
    ) -> FeatureAvailabilityCheck:
        """
        检查特征在当前回放时间是否可用
        
        Args:
            feature_name: 特征名称
            feature_timestamp: 特征的计算时间戳（K线开盘时间）
            replay_clock: 当前回放时间戳
        
        Returns:
            FeatureAvailabilityCheck: 检查结果
        """
        rule = self._rules.get(feature_name)
        
        if rule is None:
            return FeatureAvailabilityCheck(
                feature_name=feature_name,
                status=FeatureAvailabilityStatus.UNKNOWN,
                replay_clock=replay_clock,
                source_time=feature_timestamp,
                available_at=feature_timestamp,
                delay_ms=0,
                message="Unknown feature, assuming available"
            )
        
        available_at = feature_timestamp + rule.delay_ms
        
        if rule.aggregation_period_ms:
            period_start = (feature_timestamp // rule.aggregation_period_ms) * rule.aggregation_period_ms
            period_end = period_start + rule.aggregation_period_ms
            available_at = period_end
        
        if replay_clock >= available_at:
            return FeatureAvailabilityCheck(
                feature_name=feature_name,
                status=FeatureAvailabilityStatus.AVAILABLE,
                replay_clock=replay_clock,
                source_time=feature_timestamp,
                available_at=available_at,
                delay_ms=rule.delay_ms,
                message=f"Feature available (delay: {rule.delay_ms}ms)"
            )
        else:
            return FeatureAvailabilityCheck(
                feature_name=feature_name,
                status=FeatureAvailabilityStatus.NOT_YET_AVAILABLE,
                replay_clock=replay_clock,
                source_time=feature_timestamp,
                available_at=available_at,
                delay_ms=rule.delay_ms,
                message=f"Feature not available until {available_at}, current: {replay_clock}"
            )
    
    def filter_available_features(
        self,
        features: Dict[str, float],
        feature_timestamps: Dict[str, int],
        replay_clock: int
    ) -> Dict[str, float]:
        """
        过滤出当前可用的特征
        
        Args:
            features: 特征字典 {feature_name: value}
            feature_timestamps: 特征时间戳字典 {feature_name: timestamp}
            replay_clock: 当前回放时间戳
        
        Returns:
            Dict[str, float]: 可用的特征字典
        """
        available_features = {}
        blocked_features = []
        
        for feature_name, value in features.items():
            feature_ts = feature_timestamps.get(feature_name, replay_clock)
            
            check = self.check_availability(feature_name, feature_ts, replay_clock)
            
            if check.status == FeatureAvailabilityStatus.AVAILABLE:
                available_features[feature_name] = value
            else:
                blocked_features.append((feature_name, check.message))
        
        if blocked_features:
            logger.debug(
                f"Blocked {len(blocked_features)} features at replay_clock={replay_clock}: "
                f"{[f[0] for f in blocked_features[:5]]}"
            )
        
        return available_features
    
    def get_feature_available_at(
        self,
        feature_name: str,
        feature_timestamp: int
    ) -> int:
        """
        获取特征可用的时间戳
        
        Args:
            feature_name: 特征名称
            feature_timestamp: 特征的计算时间戳
        
        Returns:
            int: 特征可用的时间戳
        """
        rule = self._rules.get(feature_name)
        
        if rule is None:
            return feature_timestamp
        
        if rule.aggregation_period_ms:
            period_start = (feature_timestamp // rule.aggregation_period_ms) * rule.aggregation_period_ms
            return period_start + rule.aggregation_period_ms
        
        return feature_timestamp + rule.delay_ms
    
    def validate_dataframe(
        self,
        df: pd.DataFrame,
        timestamp_col: str = "timestamp"
    ) -> List[Dict[str, Any]]:
        """
        验证 DataFrame 中的特征时间因果关系
        
        Args:
            df: 包含特征的 DataFrame
            timestamp_col: 时间戳列名
        
        Returns:
            List[Dict]: 潜在泄漏警告列表
        """
        warnings = []
        
        for feature_name in df.columns:
            if feature_name == timestamp_col:
                continue
            
            rule = self._rules.get(feature_name)
            if rule and rule.delay_ms > 0:
                if rule.aggregation_period_ms:
                    period_ms = rule.aggregation_period_ms
                    
                    for idx in range(len(df)):
                        ts = df[timestamp_col].iloc[idx]
                        period_end = ((ts // period_ms) + 1) * period_ms
                        
                        if ts < period_end:
                            warnings.append({
                                "type": "multi_period_leak",
                                "feature": feature_name,
                                "row": idx,
                                "timestamp": ts,
                                "period_end": period_end,
                                "message": f"{feature_name} at {ts} uses incomplete period ending at {period_end}"
                            })
                            break
        
        return warnings
    
    def get_all_rules(self) -> Dict[str, FeatureAvailabilityRule]:
        """获取所有特征可用性规则"""
        return self._rules.copy()
    
    def add_custom_rule(self, rule: FeatureAvailabilityRule):
        """添加自定义规则"""
        self._rules[rule.feature_name] = rule


_guard_instance: Optional[FeatureAvailabilityGuard] = None


def get_feature_availability_guard(interval_ms: int = 60000) -> FeatureAvailabilityGuard:
    """获取特征可用性守卫单例"""
    global _guard_instance
    if _guard_instance is None:
        _guard_instance = FeatureAvailabilityGuard(interval_ms)
    return _guard_instance
