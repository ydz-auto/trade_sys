"""
Multi-Source Collector - 多数据源采集、交叉验证、融合工具
"""

import asyncio
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime

from .base_collector import CollectorResult, SourceConfig
from infrastructure.logging import get_logger

logger = get_logger("collectors.multi_source")


@dataclass
class FusionResult:
    """融合结果"""
    data: Any
    sources_used: List[str]
    confidence: float
    total_weight: float
    validation_notes: List[str] = field(default_factory=list)
    method: str = "weighted_average"


class CrossValidator:
    """交叉验证器"""

    def __init__(self, diff_threshold_percent: float = 10.0):
        self.diff_threshold = diff_threshold_percent / 100

    def validate_numeric(
        self,
        results: Dict[str, CollectorResult],
        weights: Dict[str, float]
    ) -> Dict[str, float]:
        """
        对数值型数据进行交叉验证
        返回调整后的权重
        """
        valid_results = {
            name: r for name, r in results.items()
            if r.success and isinstance(r.data, (int, float))
        }

        if len(valid_results) < 2:
            return weights

        values = [r.data for r in valid_results.values()]
        avg = sum(values) / len(values)

        adjusted_weights = {}
        for name, result in valid_results.items():
            deviation = abs(result.data - avg) / avg if avg != 0 else 0

            if deviation > self.diff_threshold:
                adjusted_weights[name] = weights.get(name, 1.0) * 0.5
                logger.warning(
                    f"数据偏差过大: {name}={result.data}, "
                    f"平均值={avg:.2f}, 偏差={deviation*100:.1f}%"
                )
            else:
                adjusted_weights[name] = weights.get(name, 1.0)

        return adjusted_weights


class DataFusion:
    """数据融合器"""

    @staticmethod
    def weighted_average(
        results: Dict[str, CollectorResult],
        weights: Dict[str, float]
    ) -> FusionResult:
        """加权平均融合"""
        valid = {n: r for n, r in results.items() if r.success}

        if not valid:
            return FusionResult(
                data=None,
                sources_used=[],
                confidence=0,
                total_weight=0
            )

        total_weight = sum(weights.get(n, 1.0) for n in valid.keys())
        if total_weight == 0:
            total_weight = 1.0

        numeric_results = {
            n: r for n, r in valid.items()
            if isinstance(r.data, (int, float))
        }

        if numeric_results:
            fused_value = sum(
                r.data * weights.get(n, 1.0)
                for n, r in numeric_results.items()
            ) / total_weight

            confidence = sum(
                r.confidence * weights.get(n, 1.0)
                for n, r in numeric_results.items()
            ) / total_weight
        else:
            best_name = max(valid.keys(), key=lambda n: weights.get(n, 1.0))
            fused_value = valid[best_name].data
            confidence = valid[best_name].confidence

        return FusionResult(
            data=fused_value,
            sources_used=list(valid.keys()),
            confidence=confidence,
            total_weight=total_weight,
            method="weighted_average"
        )

    @staticmethod
    def confidence_weighted(
        results: Dict[str, CollectorResult],
        weights: Dict[str, float]
    ) -> FusionResult:
        """置信度加权融合（选择最高置信度）"""
        valid = {n: r for n, r in results.items() if r.success}

        if not valid:
            return FusionResult(
                data=None,
                sources_used=[],
                confidence=0,
                total_weight=0
            )

        best_name = max(
            valid.keys(),
            key=lambda n: valid[n].confidence * weights.get(n, 1.0)
        )
        best = valid[best_name]

        return FusionResult(
            data=best.data,
            sources_used=[best_name],
            confidence=best.confidence * weights.get(best_name, 1.0),
            total_weight=weights.get(best_name, 1.0),
            method="confidence_weighted"
        )

    @staticmethod
    def multi_value_fusion(
        results: Dict[str, CollectorResult],
        weights: Dict[str, float],
        merge_func: Callable[[List[Any]], Any] = None
    ) -> FusionResult:
        """
        多值融合（如新闻、ETF列表等）
        merge_func: 自定义合并函数，默认取所有值的并集
        """
        valid = {n: r for n, r in results.items() if r.success}

        if not valid:
            return FusionResult(
                data=None,
                sources_used=[],
                confidence=0,
                total_weight=0
            )

        all_values = []
        for name, result in valid.items():
            if isinstance(result.data, list):
                all_values.extend(result.data)
            else:
                all_values.append(result.data)

        if merge_func:
            fused_data = merge_func(all_values)
        else:
            fused_data = all_values

        total_weight = sum(weights.get(n, 1.0) for n in valid.keys())
        avg_confidence = sum(r.confidence for r in valid.values()) / len(valid)

        return FusionResult(
            data=fused_data,
            sources_used=list(valid.keys()),
            confidence=avg_confidence,
            total_weight=total_weight,
            method="multi_value"
        )


class MultiSourceCollector:
    """多数据源采集器（组合基类）"""

    def __init__(
        self,
        name: str,
        sources: Dict[str, SourceConfig],
        fusion_method: str = "weighted_average"
    ):
        self.name = name
        self.sources = sources
        self.fusion_method = fusion_method
        self.cross_validator = CrossValidator()
        self.fusion = DataFusion()
        self.results: Dict[str, CollectorResult] = {}

    async def collect_all(
        self,
        collector_func: Callable[[str, SourceConfig], CollectorResult]
    ) -> FusionResult:
        """采集所有数据源并融合"""
        tasks = []
        source_names = []

        for sname, config in self.sources.items():
            if config.enabled:
                tasks.append(self._collect_with_timeout(sname, config, collector_func))
                source_names.append(sname)

        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        results = {}
        for name, result in zip(source_names, results_list):
            if isinstance(result, Exception):
                results[name] = CollectorResult(
                    success=False,
                    error=str(result),
                    source=name
                )
            elif isinstance(result, CollectorResult):
                results[name] = result
            else:
                results[name] = CollectorResult(success=False, error="Unknown error", source=name)

        self.results = results

        weights = {name: config.weight for name, config in self.sources.items() if config.enabled}
        adjusted_weights = self.cross_validator.validate_numeric(results, weights)

        if self.fusion_method == "weighted_average":
            return self.fusion.weighted_average(results, adjusted_weights)
        elif self.fusion_method == "confidence_weighted":
            return self.fusion.confidence_weighted(results, adjusted_weights)
        else:
            return self.fusion.weighted_average(results, adjusted_weights)

    async def _collect_with_timeout(
        self,
        name: str,
        config: SourceConfig,
        collector_func: Callable
    ) -> CollectorResult:
        """带超时的采集"""
        try:
            result = await asyncio.wait_for(
                collector_func(name, config),
                timeout=config.timeout
            )
            return result
        except asyncio.TimeoutError:
            return CollectorResult(
                success=False,
                error=f"采集超时 ({config.timeout}s)",
                source=name
            )
        except Exception as e:
            return CollectorResult(
                success=False,
                error=str(e),
                source=name
            )

    def get_health_status(self) -> Dict:
        """获取健康状态"""
        if not self.results:
            return {"status": "no_data"}

        success_count = sum(1 for r in self.results.values() if r.success)
        total_count = len(self.results)

        if success_count == 0:
            status = "all_failed"
        elif success_count < total_count / 2:
            status = "partial_failure"
        else:
            status = "healthy"

        return {
            "status": status,
            "success_count": success_count,
            "total_count": total_count,
            "sources": {
                name: {
                    "success": r.success,
                    "error": r.error,
                    "latency_ms": r.latency_ms
                }
                for name, r in self.results.items()
            }
        }
