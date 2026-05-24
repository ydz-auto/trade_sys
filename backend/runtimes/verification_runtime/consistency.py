"""
Consistency Testing Framework - 一致性测试框架

提供自动化的一致性测试能力：
- Live vs Replay 对比
- Runtime 一致性验证
- Cross-mode 验证
- 回归测试

基于真正的 Runtime Kernel (runtime/replay_runtime) 而非 infrastructure 层的伪 Runtime。
"""

import asyncio
from typing import Dict, List, Optional, Any, Callable, Awaitable, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import uuid

from infrastructure.logging import get_logger
from runtimes.verification_runtime.determinism import (
    DeterminismVerifier,
    VerificationResult,
    VerificationStatus,
    get_determinism_verifier,
)

logger = get_logger("runtime.verification.consistency")


class TestType(str, Enum):
    LIVE_VS_REPLAY = "live_vs_replay"
    LIVE_VS_BACKTEST = "live_vs_backtest"
    REPLAY_DETERMINISM = "replay_determinism"
    SNAPSHOT_RECOVERY = "snapshot_recovery"
    CROSS_MODE = "cross_mode"
    REGRESSION = "regression"


@dataclass
class TestCase:
    test_id: str
    test_type: TestType
    test_name: str
    description: str
    runtime_factory: Optional[Callable[[], Any]] = None
    event_generator: Optional[Callable[[], Awaitable[List[Dict[str, Any]]]]] = None
    event_source: Optional[List[Dict[str, Any]]] = None
    compare_states: Optional[Callable[[Dict, Dict], Tuple[bool, List]]] = None
    assertions: List[Callable[[Dict[str, Any]], bool]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TestReport:
    report_id: str
    test_id: str
    test_type: TestType
    test_name: str
    status: str
    passed: int
    failed: int
    skipped: int
    start_time: datetime
    end_time: datetime
    duration_ms: float
    results: List[VerificationResult] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "test_id": self.test_id,
            "test_type": self.test_type.value,
            "test_name": self.test_name,
            "status": self.status,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_ms": self.duration_ms,
            "results": [r.to_dict() for r in self.results],
            "details": self.details,
        }


@dataclass
class ComparisonResult:
    runtime_a: str
    runtime_b: str
    states_match: bool
    order_count_match: bool
    fill_count_match: bool
    capital_diff: float = 0.0
    pnl_diff: float = 0.0
    position_diff: int = 0
    differences: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "runtime_a": self.runtime_a,
            "runtime_b": self.runtime_b,
            "states_match": self.states_match,
            "order_count_match": self.order_count_match,
            "fill_count_match": self.fill_count_match,
            "capital_diff": self.capital_diff,
            "pnl_diff": self.pnl_diff,
            "position_diff": self.position_diff,
            "differences": self.differences,
        }


class ConsistencyTester:

    def __init__(self):
        self._verifier = get_determinism_verifier()
        self._test_cases: Dict[str, TestCase] = {}
        self._test_history: List[TestReport] = []

    def register_test_case(self, test_case: TestCase) -> None:
        self._test_cases[test_case.test_id] = test_case
        logger.info(f"Test case registered: {test_case.test_id} ({test_case.test_name})")

    async def run_replay_determinism_test(
        self,
        test_name: str,
        replay_runtime_factory: Callable[[], Any],
        event_source: List[Dict[str, Any]],
        runs: int = 3,
    ) -> TestReport:
        report_id = f"det_{uuid.uuid4().hex[:12]}"
        start_time = datetime.utcnow()

        try:
            logger.info(f"Starting Replay Determinism test: {test_name}")

            results = []
            for i in range(runs):
                runtime = replay_runtime_factory()
                await runtime.start_session(
                    symbol=event_source[0].get("symbol", "BTCUSDT") if event_source else "BTCUSDT",
                    start_time_ms=event_source[0].get("timestamp_ms", 0) if event_source else 0,
                    end_time_ms=event_source[-1].get("timestamp_ms", 0) if event_source else 0,
                )
                for event in event_source:
                    await runtime._process_event(event)
                state = runtime.get_session_state()
                results.append(state)
                await runtime.stop()

            first_state = results[0]
            all_match = all(
                self._dict_approx_equal(
                    first_state.__dict__ if hasattr(first_state, '__dict__') else first_state,
                    r.__dict__ if hasattr(r, '__dict__') else r,
                )
                for r in results
            )

            verification_results = []
            verification_results.append(VerificationResult(
                verification_id=f"{report_id}_determinism",
                test_name=f"{test_name} - Determinism",
                status=VerificationStatus.PASSED if all_match else VerificationStatus.FAILED,
                expected="deterministic",
                actual="deterministic" if all_match else "non-deterministic",
            ))

            end_time = datetime.utcnow()

            report = TestReport(
                report_id=report_id,
                test_id="",
                test_type=TestType.REPLAY_DETERMINISM,
                test_name=test_name,
                status="passed" if all_match else "failed",
                passed=1 if all_match else 0,
                failed=0 if all_match else 1,
                skipped=0,
                start_time=start_time,
                end_time=end_time,
                duration_ms=(end_time - start_time).total_seconds() * 1000,
                results=verification_results,
                details={"runs": runs},
            )

            self._test_history.append(report)

            logger.info(f"Replay Determinism test completed: {test_name} - {'PASSED' if all_match else 'FAILED'}")
            return report

        except Exception as e:
            logger.error(f"Replay Determinism test failed: {e}")
            end_time = datetime.utcnow()
            return TestReport(
                report_id=report_id,
                test_id="",
                test_type=TestType.REPLAY_DETERMINISM,
                test_name=test_name,
                status="error",
                passed=0,
                failed=1,
                skipped=0,
                start_time=start_time,
                end_time=end_time,
                duration_ms=(end_time - start_time).total_seconds() * 1000,
                results=[],
                details={"error": str(e)},
            )

    async def run_snapshot_recovery_test(
        self,
        test_name: str,
        runtime: Any,
        initial_events: List[Dict[str, Any]],
        events_after_snapshot: List[Dict[str, Any]],
        snapshot_function: Callable[[], Awaitable[Dict]],
        restore_function: Callable[[Dict], Awaitable[None]],
    ) -> TestReport:
        report_id = f"snap_{uuid.uuid4().hex[:12]}"
        start_time = datetime.utcnow()

        try:
            logger.info(f"Starting Snapshot Recovery test: {test_name}")

            for event in initial_events:
                await runtime._process_event(event)

            snapshot_before = await snapshot_function()
            state_before = runtime.get_session_state()

            for event in events_after_snapshot:
                await runtime._process_event(event)

            await restore_function(snapshot_before)
            state_after_restore = runtime.get_session_state()

            state_match = self._dict_approx_equal(
                state_before.__dict__ if hasattr(state_before, '__dict__') else state_before,
                state_after_restore.__dict__ if hasattr(state_after_restore, '__dict__') else state_after_restore,
            )

            verification_results = []
            verification_results.append(VerificationResult(
                verification_id=f"{report_id}_snapshot",
                test_name=f"{test_name} - Snapshot Recovery",
                status=VerificationStatus.PASSED if state_match else VerificationStatus.FAILED,
                expected="states_match",
                actual=state_match,
            ))

            await runtime.stop()

            end_time = datetime.utcnow()

            report = TestReport(
                report_id=report_id,
                test_id="",
                test_type=TestType.SNAPSHOT_RECOVERY,
                test_name=test_name,
                status="passed" if state_match else "failed",
                passed=1 if state_match else 0,
                failed=0 if state_match else 1,
                skipped=0,
                start_time=start_time,
                end_time=end_time,
                duration_ms=(end_time - start_time).total_seconds() * 1000,
                results=verification_results,
                details={
                    "initial_event_count": len(initial_events),
                    "events_after_snapshot_count": len(events_after_snapshot),
                },
            )

            self._test_history.append(report)

            logger.info(f"Snapshot Recovery test completed: {test_name} - {'PASSED' if state_match else 'FAILED'}")
            return report

        except Exception as e:
            logger.error(f"Snapshot Recovery test failed: {e}")
            end_time = datetime.utcnow()
            return TestReport(
                report_id=report_id,
                test_id="",
                test_type=TestType.SNAPSHOT_RECOVERY,
                test_name=test_name,
                status="error",
                passed=0,
                failed=1,
                skipped=0,
                start_time=start_time,
                end_time=end_time,
                duration_ms=(end_time - start_time).total_seconds() * 1000,
                results=[],
                details={"error": str(e)},
            )

    def _dict_approx_equal(
        self,
        a: Any,
        b: Any,
        tolerance: float = 1e-6,
    ) -> bool:
        if type(a) != type(b):
            return False

        if isinstance(a, dict):
            if set(a.keys()) != set(b.keys()):
                return False
            return all(self._dict_approx_equal(a[k], b[k], tolerance) for k in a.keys())

        elif isinstance(a, (list, tuple)):
            if len(a) != len(b):
                return False
            return all(self._dict_approx_equal(x, y, tolerance) for x, y in zip(a, b))

        elif isinstance(a, (int, float)):
            if a == b:
                return True
            if abs(a) < tolerance:
                return abs(b) < tolerance
            return abs(a - b) / abs(a) < tolerance

        else:
            return a == b

    def get_test_history(self) -> List[TestReport]:
        return self._test_history.copy()

    def get_latest_report(self) -> Optional[TestReport]:
        return self._test_history[-1] if self._test_history else None

    def get_summary(self) -> Dict[str, Any]:
        total = len(self._test_history)
        passed = sum(1 for r in self._test_history if r.status == "passed")
        failed = sum(1 for r in self._test_history if r.status == "failed")
        error = sum(1 for r in self._test_history if r.status == "error")

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "error": error,
            "pass_rate": passed / total if total > 0 else 0,
            "latest_report": self.get_latest_report().to_dict() if self.get_latest_report() else None,
        }


_tester: Optional[ConsistencyTester] = None


def get_consistency_tester() -> ConsistencyTester:
    global _tester
    if _tester is None:
        _tester = ConsistencyTester()
    return _tester
