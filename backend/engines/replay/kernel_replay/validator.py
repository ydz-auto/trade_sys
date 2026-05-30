"""
Deterministic Validator - 确定性验证器

核心职责:
- 验证两次回放结果是否一致
- 验证 Replay 与 Live 记录是否一致
- 生成详细的验证报告
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from pathlib import Path
import json
from datetime import datetime

from engines.replay.kernel_replay.event_log import (
    EventLog,
)
from engines.replay.kernel_replay.state_capture import (
    StateCapture,
    StateSnapshot,
)
import logging

logger = logging.getLogger(__name__)


class ValidationLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    FATAL = "fatal"


@dataclass
class ValidationIssue:
    level: ValidationLevel
    category: str
    message: str
    sequence_number: int
    event_id: Optional[str]
    details: Optional[Dict[str, Any]] = None


@dataclass
class ValidationResult:
    is_consistent: bool
    total_events: int
    total_snapshots: int
    issues: List[ValidationIssue]
    summary: Dict[str, Any]
    report_time_ms: int

    def has_fatal(self) -> bool:
        return any(i.level == ValidationLevel.FATAL for i in self.issues)

    def has_critical(self) -> bool:
        return any(i.level in [ValidationLevel.FATAL, ValidationLevel.CRITICAL] for i in self.issues)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_consistent": self.is_consistent,
            "total_events": self.total_events,
            "total_snapshots": self.total_snapshots,
            "issues": [
                {
                    "level": i.level.value,
                    "category": i.category,
                    "message": i.message,
                    "sequence_number": i.sequence_number,
                    "event_id": i.event_id,
                    "details": i.details,
                }
                for i in self.issues
            ],
            "summary": self.summary,
            "report_time_ms": self.report_time_ms,
        }


class DeterminismValidator:

    def __init__(self):
        self._issues: List[ValidationIssue] = []

    def validate_replay_replay(
        self,
        capture_a: StateCapture,
        capture_b: StateCapture,
        name_a: str = "replay1",
        name_b: str = "replay2",
    ) -> ValidationResult:
        self._issues = []
        logger.info(f"Validating replay-replay: {name_a} vs {name_b}")

        if capture_a.count != capture_b.count:
            self._issues.append(ValidationIssue(
                level=ValidationLevel.CRITICAL,
                category="snapshot_count",
                message=f"Snapshot count mismatch: {capture_a.count} vs {capture_b.count}",
                sequence_number=-1,
                event_id=None,
            ))

        max_count = max(capture_a.count, capture_b.count)

        index_a = {(s.sequence_number, s.capture_point): s for s in capture_a._snapshots}
        index_b = {(s.sequence_number, s.capture_point): s for s in capture_b._snapshots}

        all_keys = set(index_a.keys()).union(set(index_b.keys()))

        for (seq_num, point) in sorted(all_keys):
            s_a = index_a.get((seq_num, point))
            s_b = index_b.get((seq_num, point))

            if s_a is None:
                self._issues.append(ValidationIssue(
                    level=ValidationLevel.CRITICAL,
                    category="missing_snapshot",
                    message=f"Missing snapshot in {name_a}: seq={seq_num}, point={point}",
                    sequence_number=seq_num,
                    event_id=s_b.event_id if s_b else None,
                ))
                continue

            if s_b is None:
                self._issues.append(ValidationIssue(
                    level=ValidationLevel.CRITICAL,
                    category="missing_snapshot",
                    message=f"Missing snapshot in {name_b}: seq={seq_num}, point={point}",
                    sequence_number=seq_num,
                    event_id=s_a.event_id if s_a else None,
                ))
                continue

            is_consistent, differences = StateCapture.compare_states(s_a, s_b)
            if not is_consistent:
                self._issues.append(ValidationIssue(
                    level=ValidationLevel.CRITICAL,
                    category="state_mismatch",
                    message=f"State mismatch at seq={seq_num}, point={point}",
                    sequence_number=seq_num,
                    event_id=s_a.event_id,
                    details=differences,
                ))

        is_consistent = len(self._issues) == 0
        summary = {
            f"{name_a}_snapshots": capture_a.count,
            f"{name_b}_snapshots": capture_b.count,
            "total_issues": len(self._issues),
            "fatal_issues": sum(1 for i in self._issues if i.level == ValidationLevel.FATAL),
            "critical_issues": sum(1 for i in self._issues if i.level == ValidationLevel.CRITICAL),
            "warning_issues": sum(1 for i in self._issues if i.level == ValidationLevel.WARNING),
        }

        result = ValidationResult(
            is_consistent=is_consistent,
            total_events=0,
            total_snapshots=max_count,
            issues=self._issues.copy(),
            summary=summary,
            report_time_ms=int(datetime.utcnow().timestamp() * 1000),
        )

        logger.info(f"Validation complete: is_consistent={is_consistent}, issues={len(self._issues)}")
        return result

    def validate_event_logs(
        self,
        log_a: EventLog,
        log_b: EventLog,
        name_a: str = "log1",
        name_b: str = "log2",
    ) -> ValidationResult:
        self._issues = []
        logger.info(f"Validating event logs: {name_a} vs {name_b}")

        if log_a.count != log_b.count:
            self._issues.append(ValidationIssue(
                level=ValidationLevel.CRITICAL,
                category="event_count",
                message=f"Event count mismatch: {log_a.count} vs {log_b.count}",
                sequence_number=-1,
                event_id=None,
            ))

        min_count = min(log_a.count, log_b.count)

        events_a = log_a.get_events()
        events_b = log_b.get_events()

        for i in range(min_count):
            e_a = events_a[i]
            e_b = events_b[i]

            if e_a.sequence_number != e_b.sequence_number:
                self._issues.append(ValidationIssue(
                    level=ValidationLevel.CRITICAL,
                    category="seq_mismatch",
                    message=f"Sequence number mismatch: {e_a.sequence_number} vs {e_b.sequence_number}",
                    sequence_number=e_a.sequence_number,
                    event_id=e_a.event_id,
                ))

            if e_a.event_time_ms != e_b.event_time_ms:
                self._issues.append(ValidationIssue(
                    level=ValidationLevel.CRITICAL,
                    category="time_mismatch",
                    message=f"Event time mismatch: {e_a.event_time_ms} vs {e_b.event_time_ms}",
                    sequence_number=e_a.sequence_number,
                    event_id=e_a.event_id,
                ))

            if e_a.available_time_ms != e_b.available_time_ms:
                self._issues.append(ValidationIssue(
                    level=ValidationLevel.CRITICAL,
                    category="available_time_mismatch",
                    message=f"Available time mismatch: {e_a.available_time_ms} vs {e_b.available_time_ms}",
                    sequence_number=e_a.sequence_number,
                    event_id=e_a.event_id,
                ))

        is_consistent = len(self._issues) == 0
        summary = {
            f"{name_a}_events": log_a.count,
            f"{name_b}_events": log_b.count,
            "total_issues": len(self._issues),
            "fatal_issues": sum(1 for i in self._issues if i.level == ValidationLevel.FATAL),
            "critical_issues": sum(1 for i in self._issues if i.level == ValidationLevel.CRITICAL),
        }

        result = ValidationResult(
            is_consistent=is_consistent,
            total_events=log_a.count,
            total_snapshots=0,
            issues=self._issues.copy(),
            summary=summary,
            report_time_ms=int(datetime.utcnow().timestamp() * 1000),
        )

        return result

    def save_report(
        self,
        result: ValidationResult,
        path: Path,
    ) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)

        logger.info(f"Saved validation report to {path}")
        return path

    @staticmethod
    def print_summary(result: ValidationResult) -> None:
        print("=" * 80)
        print("DETERMINISTIC VALIDATION REPORT")
        print("=" * 80)
        print(f"Consistent: {'YES' if result.is_consistent else 'NO'}")
        print(f"Total Events: {result.total_events}")
        print(f"Total Snapshots: {result.total_snapshots}")
        print(f"Total Issues: {len(result.issues)}")

        if result.issues:
            print("\nIssues:")
            for i in result.issues[:10]:
                print(f"  [{i.level.value.upper()}] [{i.category}] (seq={i.sequence_number}) {i.message}")
            if len(result.issues) > 10:
                print(f"  ... and {len(result.issues) - 10} more")

        print("\nSummary:")
        for k, v in result.summary.items():
            print(f"  {k}: {v}")

        print("=" * 80)
