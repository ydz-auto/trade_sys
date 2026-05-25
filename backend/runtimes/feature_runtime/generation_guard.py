"""
Feature Generation Guard - 特征生成守卫

确保所有特征生成代码都经过 FeatureAvailabilityGuard 检查

使用方式：
1. 装饰器模式：@with_feature_guard
2. 包装器模式：GuardedFeatureExtractor
3. 上下文管理器：feature_generation_context
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from functools import wraps
import pandas as pd

import logging
from domain.feature.availability import (
    SystematicAvailabilityGuard,
    get_systematic_guard,
    AvailabilityStatus,
)

logger = logging.getLogger(__name__)


@dataclass
class FeatureGenerationResult:
    """特征生成结果"""
    timestamp: int
    features: Dict[str, Any]
    available_at_times: Dict[str, int]
    blocked_features: List[str]
    warnings: List[str]
    source: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "features": self.features,
            "available_at_times": self.available_at_times,
            "blocked_features": self.blocked_features,
            "warnings": self.warnings,
            "source": self.source,
        }


class FeatureGenerationContext:
    """
    特征生成上下文
    
    用于跟踪特征生成过程中的时间纪律
    """
    
    def __init__(
        self,
        replay_clock: int,
        guard: Optional[SystematicAvailabilityGuard] = None,
        strict_mode: bool = False,
        source: str = "unknown",
    ):
        self.replay_clock = replay_clock
        self.guard = guard or get_systematic_guard()
        self.strict_mode = strict_mode
        self.source = source
        
        self._generated_features: Dict[str, Any] = {}
        self._available_at_times: Dict[str, int] = {}
        self._blocked_features: List[str] = []
        self._warnings: List[str] = []
    
    def add_feature(
        self,
        feature_name: str,
        value: Any,
        feature_timestamp: int,
        check_availability: bool = True,
    ) -> bool:
        """
        添加特征
        
        Args:
            feature_name: 特征名称
            value: 特征值
            feature_timestamp: 特征计算时间戳
            check_availability: 是否检查可用性
        
        Returns:
            bool: 特征是否被接受
        """
        if check_availability:
            status = self.guard.check(
                feature_name=feature_name,
                feature_timestamp=feature_timestamp,
                query_time=self.replay_clock,
            )
            
            if status != AvailabilityStatus.AVAILABLE:
                self._blocked_features.append(feature_name)
                self._warnings.append(
                    f"Feature {feature_name} blocked: {status.value}"
                )
                
                if self.strict_mode:
                    raise ValueError(f"Feature {feature_name} not available at {self.replay_clock}")
                
                return False
            
            # Get available_at time
            rule = self.guard.get_rule(feature_name)
            if rule:
                from infrastructure.utilities.runtime_clock import get_clock
                self._available_at_times[feature_name] = rule.compute_available_at(feature_timestamp, get_clock())
            else:
                self._available_at_times[feature_name] = feature_timestamp
        
        self._generated_features[feature_name] = value
        return True
    
    def add_features_batch(
        self,
        features: Dict[str, Any],
        feature_timestamp: int,
        check_availability: bool = True,
    ) -> Dict[str, bool]:
        """批量添加特征"""
        results = {}
        for name, value in features.items():
            results[name] = self.add_feature(name, value, feature_timestamp, check_availability)
        return results
    
    def get_result(self) -> FeatureGenerationResult:
        """获取生成结果"""
        return FeatureGenerationResult(
            timestamp=self.replay_clock,
            features=self._generated_features.copy(),
            available_at_times=self._available_at_times.copy(),
            blocked_features=self._blocked_features.copy(),
            warnings=self._warnings.copy(),
            source=self.source,
        )
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            result = self.get_result()
            logger.debug(
                f"Feature generation completed: {len(result.features)} features, "
                f"{len(result.blocked_features)} blocked"
            )
        return False


def with_feature_guard(
    feature_names: Optional[List[str]] = None,
    strict_mode: bool = False,
):
    """
    特征生成守卫装饰器
    
    用法：
        @with_feature_guard(feature_names=["volatility_1h", "trend_1h"])
        def extract_volatility_features(df, timestamp):
            return {"volatility_1h": ..., "trend_1h": ...}
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            replay_clock = kwargs.get("replay_clock") or kwargs.get("timestamp")
            if replay_clock is None and len(args) > 0:
                if isinstance(args[0], pd.DataFrame) and "timestamp" in args[0].columns:
                    replay_clock = args[0]["timestamp"].iloc[-1]
                elif isinstance(args[0], (int, float)):
                    replay_clock = int(args[0])
            
            if replay_clock is None:
                logger.warning(f"Cannot determine replay_clock for {func.__name__}")
                return func(*args, **kwargs)
            
            guard = get_systematic_guard()
            result = func(*args, **kwargs)
            
            if not isinstance(result, dict):
                return result
            
            checked_features = {}
            blocked = []
            warnings_list = []
            
            for name, value in result.items():
                if feature_names and name not in feature_names:
                    checked_features[name] = value
                    continue
                
                if name in ["timestamp", "symbol", "exchange", "datetime"]:
                    checked_features[name] = value
                    continue
                
                status = guard.check(
                    feature_name=name,
                    feature_timestamp=replay_clock,
                    query_time=replay_clock,
                )
                
                if status == AvailabilityStatus.AVAILABLE:
                    checked_features[name] = value
                else:
                    blocked.append(name)
                    warnings_list.append(f"{name}: {status.value}")
                    
                    if strict_mode:
                        raise ValueError(f"Feature {name} not available: {status.value}")
            
            if blocked:
                logger.warning(
                    f"Feature guard blocked {len(blocked)} features in {func.__name__}: "
                    f"{blocked[:5]}"
                )
            
            return checked_features
        
        return wrapper
    return decorator


class GuardedFeatureExtractor:
    """
    带守卫的特征提取器基类
    
    所有特征提取器应该继承这个类
    """
    
    FEATURE_CATEGORY: str = "unknown"
    REQUIRES_CLOSED_CANDLE: bool = False
    AGGREGATION_PERIOD_MS: Optional[int] = None
    
    def __init__(
        self,
        guard: Optional[SystematicAvailabilityGuard] = None,
        strict_mode: bool = False,
    ):
        self.guard = guard or get_systematic_guard()
        self.strict_mode = strict_mode
        self._extraction_log: List[Dict[str, Any]] = []
    
    def extract(
        self,
        data: Any,
        timestamp: int,
        **kwargs,
    ) -> FeatureGenerationResult:
        """
        提取特征（带守卫检查）
        
        子类应该实现 _extract_features 方法
        """
        with FeatureGenerationContext(
            replay_clock=timestamp,
            guard=self.guard,
            strict_mode=self.strict_mode,
            source=self.__class__.__name__,
        ) as ctx:
            raw_features = self._extract_features(data, timestamp, **kwargs)
            
            for name, value in raw_features.items():
                if name in ["timestamp", "symbol", "exchange", "datetime"]:
                    ctx.add_feature(name, value, timestamp, check_availability=False)
                else:
                    ctx.add_feature(name, value, timestamp, check_availability=True)
            
            result = ctx.get_result()
        
        self._extraction_log.append({
            "timestamp": timestamp,
            "feature_count": len(result.features),
            "blocked_count": len(result.blocked_features),
            "source": self.__class__.__name__,
        })
        
        return result
    
    def _extract_features(
        self,
        data: Any,
        timestamp: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        子类实现此方法
        
        返回原始特征字典，守卫会自动检查
        """
        raise NotImplementedError("Subclasses must implement _extract_features")
    
    def get_extraction_stats(self) -> Dict[str, Any]:
        """获取提取统计"""
        total = len(self._extraction_log)
        if total == 0:
            return {"total_extractions": 0}
        
        total_features = sum(log["feature_count"] for log in self._extraction_log)
        total_blocked = sum(log["blocked_count"] for log in self._extraction_log)
        
        return {
            "total_extractions": total,
            "total_features": total_features,
            "total_blocked": total_blocked,
            "avg_features_per_extraction": total_features / total,
            "block_rate": total_blocked / (total_features + total_blocked) if (total_features + total_blocked) > 0 else 0,
        }


class FeatureExtractionAuditor:
    """
    特征提取审计器
    
    用于审计所有特征提取代码是否正确使用守卫
    """
    
    def __init__(self):
        self._extraction_records: List[Dict[str, Any]] = []
        self._unguarded_extractions: List[Dict[str, Any]] = []
    
    def record_extraction(
        self,
        extractor_name: str,
        features: Dict[str, Any],
        timestamp: int,
        guarded: bool,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """记录特征提取"""
        record = {
            "extractor_name": extractor_name,
            "features": list(features.keys()),
            "timestamp": timestamp,
            "guarded": guarded,
            "metadata": metadata or {},
            "recorded_at": datetime.utcnow().isoformat(),
        }
        
        self._extraction_records.append(record)
        
        if not guarded:
            self._unguarded_extractions.append(record)
            logger.warning(
                f"Unguarded feature extraction detected: {extractor_name} "
                f"at {timestamp}, features: {list(features.keys())[:5]}"
            )
    
    def audit_extractor_class(self, extractor_class: type) -> Dict[str, Any]:
        """审计特征提取器类"""
        result = {
            "class_name": extractor_class.__name__,
            "has_guard": False,
            "uses_context": False,
            "has_decorator": False,
            "issues": [],
        }
        
        if hasattr(extractor_class, "guard") or hasattr(extractor_class, "_guard"):
            result["has_guard"] = True
        
        if hasattr(extractor_class, "FEATURE_CATEGORY"):
            result["feature_category"] = extractor_class.FEATURE_CATEGORY
        else:
            result["issues"].append("Missing FEATURE_CATEGORY")
        
        if hasattr(extractor_class, "REQUIRES_CLOSED_CANDLE"):
            result["requires_closed_candle"] = extractor_class.REQUIRES_CLOSED_CANDLE
        else:
            result["issues"].append("Missing REQUIRES_CLOSED_CANDLE definition")
        
        if hasattr(extractor_class, "AGGREGATION_PERIOD_MS"):
            result["aggregation_period_ms"] = extractor_class.AGGREGATION_PERIOD_MS
        
        for name, method in extractor_class.__dict__.items():
            if callable(method) and hasattr(method, "_feature_guarded"):
                result["has_decorator"] = True
        
        return result
    
    def get_audit_report(self) -> Dict[str, Any]:
        """获取审计报告"""
        total = len(self._extraction_records)
        unguarded = len(self._unguarded_extractions)
        
        extractor_stats = {}
        for record in self._extraction_records:
            name = record["extractor_name"]
            if name not in extractor_stats:
                extractor_stats[name] = {
                    "total": 0,
                    "guarded": 0,
                    "unguarded": 0,
                }
            extractor_stats[name]["total"] += 1
            if record["guarded"]:
                extractor_stats[name]["guarded"] += 1
            else:
                extractor_stats[name]["unguarded"] += 1
        
        return {
            "total_extractions": total,
            "unguarded_extractions": unguarded,
            "guard_rate": (total - unguarded) / total if total > 0 else 0,
            "extractor_stats": extractor_stats,
            "unguarded_samples": self._unguarded_extractions[:10],
        }


_auditor: Optional[FeatureExtractionAuditor] = None


def get_feature_auditor() -> FeatureExtractionAuditor:
    """获取特征审计器实例"""
    global _auditor
    if _auditor is None:
        _auditor = FeatureExtractionAuditor()
    return _auditor


def audit_all_extractors() -> Dict[str, Any]:
    """
    审计所有特征提取器
    
    扫描 domain/feature/ 目录下的所有提取器
    """
    import importlib
    import inspect
    from pathlib import Path
    
    auditor = get_feature_auditor()
    results = {
        "scanned_modules": [],
        "extractor_classes": [],
        "issues": [],
    }
    
    feature_modules = [
        "domain.feature.trade.trade_feature",
        "domain.feature.microstructure.microstructure_feature",
        "domain.feature.oi.oi_funding_correlation",
        "domain.feature.liquidation.liquidation_feature",
    ]
    
    for module_name in feature_modules:
        try:
            module = importlib.import_module(module_name)
            results["scanned_modules"].append(module_name)
            
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if "Extractor" in name or "Feature" in name:
                    audit_result = auditor.audit_extractor_class(obj)
                    audit_result["module"] = module_name
                    results["extractor_classes"].append(audit_result)
                    
                    if audit_result["issues"]:
                        results["issues"].append({
                            "class": name,
                            "module": module_name,
                            "issues": audit_result["issues"],
                        })
        
        except Exception as e:
            results["issues"].append({
                "module": module_name,
                "error": str(e),
            })
    
    return results
