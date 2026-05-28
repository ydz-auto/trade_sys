
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Dict, Optional

from infrastructure.logging import get_logger
from research.leakage_audit.timeline import (
    AvailabilityTimeline,
    TimelineEvent,
    EventType,
)

logger = get_logger("research.leakage_audit")


class LeakageCategory(Enum):
    FEATURE_TOO_EARLY = "feature_too_early"
    PARTIAL_CANDLE = "partial_candle"
    FUTURE_DATA = "future_data"
    LABEL_LOOKAHEAD = "label_lookahead"
    CACHE_LEAKAGE = "cache_leakage"
    REGIME_LOOKAHEAD = "regime_lookahead"


@dataclass
class LeakageIssue:
    category: LeakageCategory
    description: str
    event_id: Optional[str] = None
    event_type: Optional[EventType] = None
    timestamp_ms: Optional[int] = None
    affected_symbol: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    severity: str = "warning"

    def to_dict(self) -> dict:
        return {
            "category": self.category.value,
            "description": self.description,
            "event_id": self.event_id,
            "event_type": self.event_type.value if self.event_type else None,
            "timestamp_ms": self.timestamp_ms,
            "affected_symbol": self.affected_symbol,
            "metadata": self.metadata,
            "severity": self.severity,
        }


@dataclass
class LeakageAuditResult:
    total_issues: int = 0
    issues: List[LeakageIssue] = field(default_factory=list)
    critical_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    timeline_events_checked: int = 0

    @property
    def has_critical(self) -> bool:
        return self.critical_count > 0

    def add_issue(self, issue: LeakageIssue) -> None:
        self.issues.append(issue)
        self.total_issues += 1
        if issue.severity == "critical":
            self.critical_count += 1
        elif issue.severity == "warning":
            self.warning_count += 1
        else:
            self.info_count += 1

    def to_dict(self) -> dict:
        return {
            "total_issues": self.total_issues,
            "critical_count": self.critical_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "timeline_events_checked": self.timeline_events_checked,
            "issues": [i.to_dict() for i in self.issues],
            "has_critical": self.has_critical,
        }


class LeakageAudit:
    def __init__(self):
        self._issues: List[LeakageIssue] = []
        self._timeline: Optional[AvailabilityTimeline] = None

    def set_timeline(self, timeline: AvailabilityTimeline) -> None:
        self._timeline = timeline

    def audit(self) -> LeakageAuditResult:
        if self._timeline is None:
            raise ValueError("Timeline not set. Call set_timeline() first.")

        result = LeakageAuditResult()
        result.timeline_events_checked = len(self._timeline.events)

        self._check_feature_signal_chronology(result)
        self._check_order_vs_signal_chronology(result)
        self._check_no_future_data_in_timeline(result)

        logger.info(
            f"Leakage audit complete: {result.total_issues} issues "
            f"({result.critical_count} critical, {result.warning_count} warnings)"
        )

        return result

    def _check_feature_signal_chronology(self, result: LeakageAuditResult) -> None:
        signals = self._timeline.get_events_by_type(EventType.SIGNAL_GENERATED)
        features = self._timeline.get_events_by_type(EventType.FEATURE_AVAILABLE)

        feature_index: Dict[str, TimelineEvent] = {
            f.metadata["feature_name"]: f for f in features
        }

        for signal in signals:
            parent_feature_names = signal.metadata.get("parent_feature_ids", [])

            for feature_name in parent_feature_names:
                feature = feature_index.get(feature_name)
                if not feature:
                    continue

                if signal.timestamp_ms < feature.timestamp_ms:
                    issue = LeakageIssue(
                        category=LeakageCategory.FEATURE_TOO_EARLY,
                        description=(
                            f"Signal {signal.metadata.get('signal_name')} generated "
                            f"before feature {feature_name} available"
                        ),
                        event_id=signal.event_id,
                        event_type=signal.event_type,
                        timestamp_ms=signal.timestamp_ms,
                        affected_symbol=signal.symbol,
                        metadata={
                            "signal_ts": signal.timestamp_ms,
                            "feature_ts": feature.timestamp_ms,
                            "feature_name": feature_name,
                        },
                        severity="critical",
                    )
                    result.add_issue(issue)

    def _check_order_vs_signal_chronology(self, result: LeakageAuditResult) -> None:
        orders = self._timeline.get_events_by_type(EventType.ORDER_SUBMITTED)
        signals = self._timeline.get_events_by_type(EventType.SIGNAL_GENERATED)
        signals_by_id: Dict[str, TimelineEvent] = {s.event_id: s for s in signals}

        for order in orders:
            signal_id = order.metadata.get("signal_id")
            if not signal_id:
                continue

            signal = signals_by_id.get(signal_id)
            if not signal:
                continue

            if order.timestamp_ms < signal.timestamp_ms:
                issue = LeakageIssue(
                    category=LeakageCategory.FUTURE_DATA,
                    description=(
                        f"Order submitted before signal was generated"
                    ),
                    event_id=order.event_id,
                    event_type=order.event_type,
                    timestamp_ms=order.timestamp_ms,
                    affected_symbol=order.symbol,
                    metadata={
                        "order_ts": order.timestamp_ms,
                        "signal_ts": signal.timestamp_ms,
                        "signal_id": signal_id,
                    },
                    severity="critical",
                )
                result.add_issue(issue)

    def _check_no_future_data_in_timeline(self, result: LeakageAuditResult) -> None:
        sorted_events = self._timeline.sort_by_time()

        for i in range(len(sorted_events) - 1):
            earlier = sorted_events[i]
            later = sorted_events[i + 1]

            if earlier.timestamp_ms > later.timestamp_ms:
                issue = LeakageIssue(
                    category=LeakageCategory.FUTURE_DATA,
                    description=(
                        f"Timeline ordering issue: {earlier.event_type} at {earlier.timestamp_ms} "
                        f"appears after {later.event_type} at {later.timestamp_ms}"
                    ),
                    event_id=earlier.event_id,
                    event_type=earlier.event_type,
                    timestamp_ms=earlier.timestamp_ms,
                    affected_symbol=earlier.symbol,
                    metadata={
                        "earlier_type": earlier.event_type.value,
                        "earlier_ts": earlier.timestamp_ms,
                        "later_type": later.event_type.value,
                        "later_ts": later.timestamp_ms,
                    },
                    severity="warning",
                )
                result.add_issue(issue)
