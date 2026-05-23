"""
Observability - Runtime 可观测性

运行时指标监控

指标：
- signal_latency: 信号延迟
- factor_staleness: 因子陈旧度
- regime_conflict: 周期冲突
- proposal_decay: alpha衰减
- replay_divergence: replay偏移
- kafka_lag: Kafka消费延迟
- ws_latency: WebSocket延迟
- decision_latency: 端到端决策延迟
"""

import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum

from domain.logging import get_logger

logger = get_logger("observability")


class MetricType(str, Enum):
    """指标类型"""
    GAUGE = "gauge"
    COUNTER = "counter"
    HISTOGRAM = "histogram"
    RATE = "rate"


@dataclass
class MetricValue:
    """指标值"""
    name: str
    value: float
    metric_type: MetricType

    timestamp: datetime = field(default_factory=datetime.utcnow)

    labels: Dict[str, str] = field(default_factory=dict)

    unit: str = ""

    description: str = ""


@dataclass
class Alert:
    """告警"""
    alert_id: str
    name: str
    severity: str

    message: str

    metric_name: str
    metric_value: float
    threshold: float

    timestamp: datetime = field(default_factory=datetime.utcnow)

    resolved: bool = False
    resolved_at: Optional[datetime] = None


class RuntimeMetrics:
    """
    Runtime 运行时指标

    收集和跟踪系统运行时指标
    """

    def __init__(self):
        self._metrics: Dict[str, List[MetricValue]] = defaultdict(list)
        self._alerts: Dict[str, Alert] = {}

        self._latencies: Dict[str, List[float]] = defaultdict(list)

        self._stats = {
            "metrics_recorded": 0,
            "alerts_triggered": 0,
            "alerts_resolved": 0,
        }

        self._thresholds = {
            "signal_latency_ms": int(os.environ.get("METRICS_SIGNAL_LATENCY_MS", "5000")),
            "factor_staleness_minutes": int(os.environ.get("METRICS_FACTOR_STALENESS_MIN", "30")),
            "kafka_lag": int(os.environ.get("METRICS_KAFKA_LAG", "1000")),
            "ws_latency_ms": int(os.environ.get("METRICS_WS_LATENCY_MS", "1000")),
            "decision_latency_ms": int(os.environ.get("METRICS_DECISION_LATENCY_MS", "10000")),
        }

    def record_metric(
        self,
        name: str,
        value: float,
        metric_type: MetricType = MetricType.GAUGE,
        labels: Optional[Dict[str, str]] = None,
        unit: str = "",
        description: str = "",
    ) -> None:
        """记录指标"""
        metric = MetricValue(
            name=name,
            value=value,
            metric_type=metric_type,
            labels=labels or {},
            unit=unit,
            description=description,
        )

        self._metrics[name].append(metric)

        if len(self._metrics[name]) > 1000:
            self._metrics[name] = self._metrics[name][-1000:]

        self._stats["metrics_recorded"] += 1

        self._check_thresholds(name, value)

    def _check_thresholds(self, name: str, value: float) -> None:
        """检查阈值"""
        if name not in self._thresholds:
            return

        threshold = self._thresholds[name]

        is_violation = False
        severity = "warning"

        if "latency" in name or "lag" in name:
            if value > threshold:
                is_violation = True
                severity = "critical" if value > threshold * 2 else "warning"

        if "staleness" in name or "decay" in name:
            if value > threshold:
                is_violation = True
                severity = "warning"

        if "conflict" in name or "divergence" in name:
            if value > 0:
                is_violation = True
                severity = "warning"

        if is_violation and name not in self._alerts:
            self._create_alert(name, value, threshold, severity)

    def _create_alert(
        self,
        metric_name: str,
        metric_value: float,
        threshold: float,
        severity: str,
    ) -> None:
        """创建告警"""
        alert_id = f"alert_{metric_name}_{datetime.utcnow().timestamp()}"

        alert = Alert(
            alert_id=alert_id,
            name=self._get_alert_name(metric_name),
            severity=severity,
            message=self._get_alert_message(metric_name, metric_value, threshold),
            metric_name=metric_name,
            metric_value=metric_value,
            threshold=threshold,
        )

        self._alerts[metric_name] = alert
        self._stats["alerts_triggered"] += 1

        logger.warning(f"Alert triggered: {alert.name} - {alert.message}")

    def _get_alert_name(self, metric_name: str) -> str:
        """获取告警名称"""
        names = {
            "signal_latency_ms": "Signal Latency High",
            "factor_staleness_minutes": "Factor Stale",
            "regime_conflict": "Regime Conflict",
            "proposal_decay": "Alpha Decaying",
            "replay_divergence": "Replay Divergence",
            "kafka_lag": "Kafka Lag High",
            "ws_latency_ms": "WS Latency High",
            "decision_latency_ms": "Decision Latency High",
        }
        return names.get(metric_name, metric_name)

    def _get_alert_message(
        self,
        metric_name: str,
        value: float,
        threshold: float,
    ) -> str:
        """获取告警消息"""
        return f"{metric_name}: {value:.2f} (threshold: {threshold:.2f})"

    def resolve_alert(self, metric_name: str) -> None:
        """解决告警"""
        if metric_name in self._alerts:
            alert = self._alerts[metric_name]
            alert.resolved = True
            alert.resolved_at = datetime.utcnow()
            self._stats["alerts_resolved"] += 1

            logger.info(f"Alert resolved: {alert.name}")

    def record_latency(self, operation: str, latency_ms: float) -> None:
        """记录延迟"""
        self._latencies[operation].append(latency_ms)

        if len(self._latencies[operation]) > 100:
            self._latencies[operation] = self._latencies[operation][-100:]

        self.record_metric(
            name=f"{operation}_latency_ms",
            value=latency_ms,
            metric_type=MetricType.HISTOGRAM,
            unit="ms",
            description=f"{operation} latency",
        )

    def get_latency_stats(self, operation: str) -> Dict[str, float]:
        """获取延迟统计"""
        latencies = self._latencies.get(operation, [])

        if not latencies:
            return {"p50": 0, "p95": 0, "p99": 0, "avg": 0}

        sorted_latencies = sorted(latencies)
        n = len(sorted_latencies)

        return {
            "p50": sorted_latencies[int(n * 0.5)],
            "p95": sorted_latencies[int(n * 0.95)] if n > 1 else sorted_latencies[0],
            "p99": sorted_latencies[int(n * 0.99)] if n > 1 else sorted_latencies[0],
            "avg": sum(latencies) / n,
            "max": max(latencies),
            "min": min(latencies),
        }

    def record_signal_latency(self, trace_id: str, latency_ms: float) -> None:
        """记录信号延迟"""
        self.record_metric(
            name="signal_latency_ms",
            value=latency_ms,
            metric_type=MetricType.HISTOGRAM,
            labels={"trace_id": trace_id},
            unit="ms",
            description="Time from signal generation to execution",
        )

    def record_factor_staleness(
        self,
        factor_name: str,
        age_minutes: float,
    ) -> None:
        """记录因子陈旧度"""
        self.record_metric(
            name="factor_staleness_minutes",
            value=age_minutes,
            metric_type=MetricType.GAUGE,
            labels={"factor": factor_name},
            unit="min",
            description="Time since factor last update",
        )

    def record_regime_conflict(
        self,
        symbol: str,
        conflict_score: float,
    ) -> None:
        """记录周期冲突"""
        self.record_metric(
            name="regime_conflict",
            value=conflict_score,
            metric_type=MetricType.GAUGE,
            labels={"symbol": symbol},
            description="Regime alignment conflict score",
        )

    def record_proposal_decay(
        self,
        proposal_id: str,
        decay_rate: float,
    ) -> None:
        """记录alpha衰减"""
        self.record_metric(
            name="proposal_decay",
            value=decay_rate,
            metric_type=MetricType.RATE,
            labels={"proposal_id": proposal_id},
            description="Alpha decay rate",
        )

    def record_replay_divergence(
        self,
        replay_id: str,
        divergence_score: float,
    ) -> None:
        """记录replay偏移"""
        self.record_metric(
            name="replay_divergence",
            value=divergence_score,
            metric_type=MetricType.GAUGE,
            labels={"replay_id": replay_id},
            description="Divergence between replay and live",
        )

    def record_kafka_lag(
        self,
        topic: str,
        group_id: str,
        lag: int,
    ) -> None:
        """记录Kafka消费延迟"""
        self.record_metric(
            name="kafka_lag",
            value=float(lag),
            metric_type=MetricType.GAUGE,
            labels={"topic": topic, "group_id": group_id},
            description="Kafka consumer lag",
        )

    def record_ws_latency(
        self,
        channel: str,
        latency_ms: float,
    ) -> None:
        """记录WebSocket延迟"""
        self.record_metric(
            name="ws_latency_ms",
            value=latency_ms,
            metric_type=MetricType.HISTOGRAM,
            labels={"channel": channel},
            unit="ms",
            description="WebSocket message latency",
        )

    def record_decision_latency(
        self,
        trace_id: str,
        latency_ms: float,
    ) -> None:
        """记录端到端决策延迟"""
        self.record_metric(
            name="decision_latency_ms",
            value=latency_ms,
            metric_type=MetricType.HISTOGRAM,
            labels={"trace_id": trace_id},
            unit="ms",
            description="End-to-end decision latency",
        )

    def get_metrics(
        self,
        name: str,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[MetricValue]:
        """获取指标历史"""
        metrics = self._metrics.get(name, [])

        if since:
            metrics = [m for m in metrics if m.timestamp >= since]

        return metrics[-limit:]

    def get_latest_metric(self, name: str) -> Optional[MetricValue]:
        """获取最新指标值"""
        metrics = self._metrics.get(name, [])
        return metrics[-1] if metrics else None

    def get_active_alerts(self) -> List[Alert]:
        """获取活跃告警"""
        return [a for a in self._alerts.values() if not a.resolved]

    def get_all_alerts(self) -> List[Alert]:
        """获取所有告警"""
        return list(self._alerts.values())

    def get_summary(self) -> Dict[str, Any]:
        """获取指标摘要"""
        latest_metrics = {}
        for name in self._metrics:
            latest = self.get_latest_metric(name)
            if latest:
                latest_metrics[name] = {
                    "value": latest.value,
                    "timestamp": latest.timestamp.isoformat(),
                    "labels": latest.labels,
                }

        return {
            "metrics_count": len(self._metrics),
            "active_alerts": len(self.get_active_alerts()),
            "latest_metrics": latest_metrics,
            "latency_stats": {
                op: self.get_latency_stats(op)
                for op in self._latencies
            },
        }

    @property
    def stats(self) -> Dict[str, Any]:
        """获取统计"""
        return {
            **self._stats,
            "metrics_tracked": len(self._metrics),
            "active_alerts": len(self.get_active_alerts()),
        }


_runtime_metrics: Optional[RuntimeMetrics] = None


def get_runtime_metrics() -> RuntimeMetrics:
    """获取 RuntimeMetrics 单例"""
    global _runtime_metrics
    if _runtime_metrics is None:
        _runtime_metrics = RuntimeMetrics()
    return _runtime_metrics
