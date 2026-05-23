"""
Feature Time Discipline - 特征时间纪律模块

核心功能：
1. 特征可用性防护 (Feature Availability Guard)
2. 防止未来数据泄漏 (Prevent Future Data Leakage)
3. 记录特征时间戳 (Record Feature Timestamps)

关键概念：
- feature_timestamp: 特征计算的时间戳（源数据时间）
- available_at: 特征可以被使用的时间戳（通常 >= feature_timestamp）
- replay_clock: 回播/策略执行的当前时间戳
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from domain.logging import get_logger
from domain.feature.materializer.schema_registry import (
    FeatureSchemaRegistry,
    FeatureSchema,
    get_schema_registry
)

logger = get_logger("feature.time_discipline")


class LeakageSeverity(Enum):
    """数据泄漏严重程度"""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class LeakageCheckResult:
    """数据泄漏检查结果"""
    feature_name: str
    has_leakage: bool
    severity: LeakageSeverity
    message: str
    feature_timestamp: Optional[int] = None
    available_at: Optional[int] = None
    replay_clock: Optional[int] = None


@dataclass
class FeatureTimeRecord:
    """特征时间记录"""
    feature_name: str
    feature_timestamp: int  # 特征计算的时间戳（源数据时间）
    available_at: int       # 特征可以被使用的时间戳
    value: Any
    schema: Optional[FeatureSchema] = None
    
    def is_available_at(self, replay_clock: int) -> bool:
        """检查特征在指定时间是否可用"""
        return replay_clock >= self.available_at


class FeatureAvailabilityGuard:
    """
    特征可用性防护
    
    核心功能：
    1. 验证特征使用时间是否合规
    2. 防止策略提前看到未来特征
    3. 记录特征访问日志用于审计
    """
    
    def __init__(self, schema_registry: Optional[FeatureSchemaRegistry] = None):
        self.schema_registry = schema_registry or get_schema_registry()
        self.access_log: List[Dict[str, Any]] = []
        self.leakage_alerts: List[LeakageCheckResult] = []
        
        # 严格模式：发现泄漏时抛出异常
        self.strict_mode = True
        
    def check_feature_availability(
        self,
        feature_name: str,
        feature_timestamp: int,
        replay_clock: int,
        available_at: Optional[int] = None
    ) -> LeakageCheckResult:
        """
        检查特征可用性
        
        Args:
            feature_name: 特征名称
            feature_timestamp: 特征计算的时间戳
            replay_clock: 回播/策略执行的当前时间戳
            available_at: 特征可用时间戳（如果为None则自动计算）
            
        Returns:
            LeakageCheckResult: 检查结果
        """
        schema = self.schema_registry.get_schema(feature_name)
        
        # 自动计算可用时间
        if available_at is None:
            available_after = schema.available_after_periods if schema else 0
            # 简单处理：假设每个周期是1分钟（60000ms）
            # 实际应用中应该根据时间粒度动态计算
            available_at = feature_timestamp + (available_after * 60000)
        
        # 基础检查：回播时间不能早于特征可用时间
        has_leakage = replay_clock < available_at
        
        # 确定严重程度
        severity = LeakageSeverity.NONE
        message = "Feature available"
        
        if has_leakage:
            time_diff_ms = available_at - replay_clock
            time_diff_sec = time_diff_ms / 1000
            
            if time_diff_sec <= 60:
                severity = LeakageSeverity.LOW
                message = f"Minor timing issue: feature used {time_diff_sec:.1f}s early"
            elif time_diff_sec <= 300:
                severity = LeakageSeverity.MEDIUM
                message = f"Moderate leakage: feature used {time_diff_sec:.1f}s early"
            elif time_diff_sec <= 3600:
                severity = LeakageSeverity.HIGH
                message = f"Significant leakage: feature used {time_diff_sec:.1f}s early"
            else:
                severity = LeakageSeverity.CRITICAL
                message = f"Critical leakage: feature used {time_diff_sec:.1f}s early"
            
            # 检查是否是future-derived特征
            if schema and schema.is_future_derived:
                severity = LeakageSeverity.CRITICAL
                message = f"CRITICAL: Future-derived feature {feature_name} used prematurely!"
        
        result = LeakageCheckResult(
            feature_name=feature_name,
            has_leakage=has_leakage,
            severity=severity,
            message=message,
            feature_timestamp=feature_timestamp,
            available_at=available_at,
            replay_clock=replay_clock
        )
        
        # 记录访问
        self._log_access(result, schema)
        
        # 严格模式下抛出异常
        if has_leakage and self.strict_mode and severity >= LeakageSeverity.HIGH:
            raise ValueError(f"Data leakage detected: {message}")
        
        return result
    
    def _log_access(self, result: LeakageCheckResult, schema: Optional[FeatureSchema]):
        """记录特征访问日志"""
        log_entry = {
            "timestamp": int(datetime.utcnow().timestamp() * 1000),
            "feature_name": result.feature_name,
            "feature_timestamp": result.feature_timestamp,
            "available_at": result.available_at,
            "replay_clock": result.replay_clock,
            "has_leakage": result.has_leakage,
            "severity": result.severity.value,
            "message": result.message,
            "schema": {
                "available_after_periods": schema.available_after_periods if schema else 0,
                "requires_lookback": schema.requires_lookback if schema else False,
                "lookback_window": schema.lookback_window if schema else 0,
                "is_future_derived": schema.is_future_derived if schema else False
            } if schema else None
        }
        
        self.access_log.append(log_entry)
        
        if result.has_leakage:
            self.leakage_alerts.append(result)
            logger.warning(f"Leakage alert: {result.message}")
    
    def get_leakage_summary(self) -> Dict[str, Any]:
        """获取数据泄漏摘要"""
        total_checks = len(self.access_log)
        total_leaks = len(self.leakage_alerts)
        
        severity_counts = {}
        for alert in self.leakage_alerts:
            sev = alert.severity.value
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
        
        feature_leaks = {}
        for alert in self.leakage_alerts:
            feature_leaks[alert.feature_name] = feature_leaks.get(alert.feature_name, 0) + 1
        
        return {
            "total_checks": total_checks,
            "total_leaks": total_leaks,
            "leak_rate": total_leaks / total_checks if total_checks > 0 else 0,
            "severity_counts": severity_counts,
            "feature_leaks": dict(sorted(feature_leaks.items(), key=lambda x: x[1], reverse=True)[:10]),
            "recent_alerts": [
                {
                    "feature_name": a.feature_name,
                    "severity": a.severity.value,
                    "message": a.message
                }
                for a in self.leakage_alerts[-10:]
            ]
        }
    
    def validate_feature_matrix(
        self,
        feature_matrix: Any,
        replay_clock: int,
        strict: bool = True
    ) -> List[LeakageCheckResult]:
        """
        验证特征矩阵的所有特征
        
        这是一个示例方法，实际实现需要根据你的FeatureMatrix结构调整
        """
        results = []
        
        # 这里需要根据你的FeatureMatrix实际结构来实现
        # 示例逻辑：
        # for feature_name, values in feature_matrix.feature_vector.items():
        #     for i, value in enumerate(values):
        #         ts = feature_matrix.timestamps[i]
        #         result = self.check_feature_availability(
        #             feature_name, ts, replay_clock
        #         )
        #         results.append(result)
        
        logger.warning("validate_feature_matrix needs implementation for your FeatureMatrix structure")
        return results
    
    def reset(self):
        """重置防护状态"""
        self.access_log = []
        self.leakage_alerts = []


# 全局单例
_availability_guard: Optional[FeatureAvailabilityGuard] = None


def get_feature_availability_guard() -> FeatureAvailabilityGuard:
    """获取特征可用性防护单例"""
    global _availability_guard
    if _availability_guard is None:
        _availability_guard = FeatureAvailabilityGuard()
    return _availability_guard
