"""
Consistency Testing Framework - 一致性测试框架

提供自动化的一致性测试能力：
- Live vs Replay 对比
- Runtime 一致性验证
- Cross-mode 验证
- 回归测试
"""

import asyncio
from typing import Dict, List, Optional, Any, Callable, Awaitable, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import uuid

from infrastructure.logging import get_logger
from infrastructure.runtime import (
    RuntimeEngine,
    RuntimeMode,
    RuntimeConfig,
    create_live_runtime,
    create_replay_runtime,
    create_backtest_runtime,
)
from infrastructure.verification.determinism import (
    DeterminismVerifier,
    VerificationResult,
    VerificationStatus,
    get_determinism_verifier,
)

logger = get_logger("infrastructure.verification.consistency")


class TestType(str, Enum):
    """测试类型"""
    LIVE_VS_REPLAY = "live_vs_replay"
    LIVE_VS_BACKTEST = "live_vs_backtest"
    REPLAY_DETERMINISM = "replay_determinism"
    SNAPSHOT_RECOVERY = "snapshot_recovery"
    CROSS_MODE = "cross_mode"
    REGRESSION = "regression"


@dataclass
class TestCase:
    """测试用例"""
    test_id: str
    test_type: TestType
    test_name: str
    
    description: str
    
    runtimes: Dict[str, RuntimeEngine] = field(default_factory=dict)
    
    event_generator: Optional[Callable[[], Awaitable[List[Dict[str, Any]]]]] = None
    event_source: Optional[List[Dict[str, Any]]] = None
    
    compare_states: Optional[Callable[[Dict, Dict], Tuple[bool, List]]] = None
    
    assertions: List[Callable[[Dict[str, Any]], bool]] = field(default_factory=list)
    
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TestReport:
    """测试报告"""
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
    """对比结果"""
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
    """一致性测试器
    
    提供完整的一致性测试能力
    """
    
    def __init__(self):
        self._verifier = get_determinism_verifier()
        self._test_cases: Dict[str, TestCase] = {}
        self._test_history: List[TestReport] = []
    
    def register_test_case(self, test_case: TestCase) -> None:
        """注册测试用例"""
        self._test_cases[test_case.test_id] = test_case
        logger.info(f"Test case registered: {test_case.test_id} ({test_case.test_name})")
    
    async def run_live_vs_replay_test(
        self,
        test_name: str,
        live_runtime: RuntimeEngine,
        replay_runtime: RuntimeEngine,
        event_source: List[Dict[str, Any]],
        compare_function: Optional[Callable[[Dict, Dict], bool]] = None,
    ) -> TestReport:
        """运行 Live vs Replay 测试"""
        report_id = f"lvr_{uuid.uuid4().hex[:12]}"
        start_time = datetime.utcnow()
        
        try:
            logger.info(f"Starting Live vs Replay test: {test_name}")
            
            await live_runtime.initialize()
            await live_runtime.start()
            
            live_events = []
            for event in event_source:
                result = await live_runtime.process_event(event)
                live_events.append({"event": event, "result": result})
            await live_runtime.stop()
            
            live_state = live_runtime.get_state()
            
            await replay_runtime.initialize()
            await replay_runtime.start()
            
            replay_events = []
            for event in event_source:
                result = await replay_runtime.process_event(event)
                replay_events.append({"event": event, "result": result})
            await replay_runtime.stop()
            
            replay_state = replay_runtime.get_state()
            
            comparison = self._compare_runtime_states(
                "live", live_state,
                "replay", replay_state,
                compare_function,
            )
            
            results = []
            if comparison.states_match:
                results.append(VerificationResult(
                    verification_id=f"{report_id}_state",
                    test_name=f"{test_name} - State Match",
                    status=VerificationStatus.PASSED,
                    expected="states_match",
                    actual=True,
                ))
            else:
                results.append(VerificationResult(
                    verification_id=f"{report_id}_state",
                    test_name=f"{test_name} - State Match",
                    status=VerificationStatus.FAILED,
                    expected="states_match",
                    actual=False,
                    differences=comparison.differences,
                ))
            
            end_time = datetime.utcnow()
            
            report = TestReport(
                report_id=report_id,
                test_id="",
                test_type=TestType.LIVE_VS_REPLAY,
                test_name=test_name,
                status="passed" if comparison.states_match else "failed",
                passed=1 if comparison.states_match else 0,
                failed=0 if comparison.states_match else 1,
                skipped=0,
                start_time=start_time,
                end_time=end_time,
                duration_ms=(end_time - start_time).total_seconds() * 1000,
                results=results,
                details={
                    "live_state": live_state.to_dict(),
                    "replay_state": replay_state.to_dict(),
                    "comparison": comparison.to_dict(),
                    "event_count": len(event_source),
                },
            )
            
            self._test_history.append(report)
            
            logger.info(f"Live vs Replay test completed: {test_name} - {'PASSED' if comparison.states_match else 'FAILED'}")
            return report
            
        except Exception as e:
            logger.error(f"Live vs Replay test failed: {e}")
            end_time = datetime.utcnow()
            return TestReport(
                report_id=report_id,
                test_id="",
                test_type=TestType.LIVE_VS_REPLAY,
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
    
    async def run_replay_determinism_test(
        self,
        test_name: str,
        replay_runtime_factory: Callable[[], RuntimeEngine],
        event_source: List[Dict[str, Any]],
        runs: int = 3,
    ) -> TestReport:
        """运行回放确定性测试"""
        report_id = f"det_{uuid.uuid4().hex[:12]}"
        start_time = datetime.utcnow()
        
        try:
            logger.info(f"Starting Replay Determinism test: {test_name}")
            
            async def run_once(run_num: int):
                runtime = replay_runtime_factory()
                await runtime.initialize()
                await runtime.start()
                
                for event in event_source:
                    await runtime.process_event(event)
                
                state = runtime.get_state()
                await runtime.stop()
                return state
            
            results = []
            for i in range(runs):
                result = await run_once(i)
                results.append(result)
            
            first_hash = str(hash(frozenset(results[0].to_dict().items())))
            all_match = all(
                str(hash(frozenset(r.to_dict().items()))) == first_hash
                for r in results
            )
            
            verification_results = []
            if all_match:
                verification_results.append(VerificationResult(
                    verification_id=f"{report_id}_determinism",
                    test_name=f"{test_name} - Determinism",
                    status=VerificationStatus.PASSED,
                    expected="deterministic",
                    actual="deterministic",
                ))
            else:
                verification_results.append(VerificationResult(
                    verification_id=f"{report_id}_determinism",
                    test_name=f"{test_name} - Determinism",
                    status=VerificationStatus.FAILED,
                    expected="deterministic",
                    actual="non-deterministic",
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
                details={
                    "runs": runs,
                    "states": [r.to_dict() for r in results],
                },
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
        runtime: RuntimeEngine,
        initial_events: List[Dict[str, Any]],
        events_after_snapshot: List[Dict[str, Any]],
        snapshot_function: Callable[[], Awaitable[Dict]],
        restore_function: Callable[[Dict], Awaitable[None]],
        process_events_function: Callable[[List], Awaitable[Dict]],
    ) -> TestReport:
        """运行快照恢复测试"""
        report_id = f"snap_{uuid.uuid4().hex[:12]}"
        start_time = datetime.utcnow()
        
        try:
            logger.info(f"Starting Snapshot Recovery test: {test_name}")
            
            await runtime.initialize()
            await runtime.start()
            
            for event in initial_events:
                await runtime.process_event(event)
            
            snapshot_before = await snapshot_function()
            
            state_before = runtime.get_state()
            
            for event in events_after_snapshot:
                await runtime.process_event(event)
            
            state_after_continue = runtime.get_state()
            
            await restore_function(snapshot_before)
            
            state_after_restore = runtime.get_state()
            
            state_match = self._compare_runtime_state_objects(state_before, state_after_restore)
            
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
                    "snapshot_before": snapshot_before,
                    "state_before": state_before.to_dict(),
                    "state_after_continue": state_after_continue.to_dict(),
                    "state_after_restore": state_after_restore.to_dict(),
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
    
    async def run_cross_mode_test(
        self,
        test_name: str,
        events: List[Dict[str, Any]],
    ) -> TestReport:
        """运行跨模式测试"""
        report_id = f"xmode_{uuid.uuid4().hex[:12]}"
        start_time = datetime.utcnow()
        
        try:
            logger.info(f"Starting Cross-Mode test: {test_name}")
            
            from datetime import datetime as dt
            start_time_dt = dt(2024, 1, 1)
            end_time_dt = dt(2024, 1, 2)
            
            live_runtime = create_live_runtime()
            replay_runtime = create_replay_runtime(start_time_dt, end_time_dt)
            backtest_runtime = create_backtest_runtime(start_time_dt, end_time_dt)
            
            runtimes = {
                "live": live_runtime,
                "replay": replay_runtime,
                "backtest": backtest_runtime,
            }
            
            results = {}
            for name, runtime in runtimes.items():
                await runtime.initialize()
                await runtime.start()
                
                for event in events:
                    await runtime.process_event(event)
                
                results[name] = runtime.get_state()
                await runtime.stop()
            
            comparisons = []
            modes = list(results.keys())
            
            for i, mode_a in enumerate(modes):
                for mode_b in modes[i+1:]:
                    comparison = self._compare_runtime_states(
                        mode_a, results[mode_a],
                        mode_b, results[mode_b],
                    )
                    comparisons.append({
                        "modes": f"{mode_a}_vs_{mode_b}",
                        **comparison.to_dict(),
                    })
            
            all_match = all(c.get("states_match", False) for c in comparisons)
            
            verification_results = []
            for comp in comparisons:
                verification_results.append(VerificationResult(
                    verification_id=f"{report_id}_{comp['modes']}",
                    test_name=f"{test_name} - {comp['modes']}",
                    status=VerificationStatus.PASSED if comp.get("states_match") else VerificationStatus.FAILED,
                    expected="states_match",
                    actual=comp.get("states_match"),
                    differences=comp.get("differences", []),
                ))
            
            end_time = datetime.utcnow()
            
            report = TestReport(
                report_id=report_id,
                test_id="",
                test_type=TestType.CROSS_MODE,
                test_name=test_name,
                status="passed" if all_match else "failed",
                passed=sum(1 for c in comparisons if c.get("states_match")),
                failed=sum(1 for c in comparisons if not c.get("states_match")),
                skipped=0,
                start_time=start_time,
                end_time=end_time,
                duration_ms=(end_time - start_time).total_seconds() * 1000,
                results=verification_results,
                details={
                    "modes": modes,
                    "comparisons": comparisons,
                    "event_count": len(events),
                },
            )
            
            self._test_history.append(report)
            
            logger.info(f"Cross-Mode test completed: {test_name} - {'PASSED' if all_match else 'FAILED'}")
            return report
            
        except Exception as e:
            logger.error(f"Cross-Mode test failed: {e}")
            end_time = datetime.utcnow()
            return TestReport(
                report_id=report_id,
                test_id="",
                test_type=TestType.CROSS_MODE,
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
    
    def _compare_runtime_states(
        self,
        name_a: str,
        state_a: Any,
        name_b: str,
        state_b: Any,
        compare_function: Optional[Callable] = None,
    ) -> ComparisonResult:
        """比较两个运行时状态"""
        if compare_function:
            match = compare_function(state_a, state_b)
        else:
            match = self._compare_runtime_state_objects(state_a, state_b)
        
        capital_diff = 0.0
        pnl_diff = 0.0
        
        if hasattr(state_a, 'capital') and hasattr(state_b, 'capital'):
            capital_diff = abs(state_a.capital - state_b.capital)
        
        if hasattr(state_a, 'pnl') and hasattr(state_b, 'pnl'):
            pnl_diff = abs(state_a.pnl - state_b.pnl)
        
        differences = []
        if not match:
            differences.append({
                "type": "state_mismatch",
                "runtime_a": name_a,
                "runtime_b": name_b,
                "capital_diff": capital_diff,
                "pnl_diff": pnl_diff,
            })
        
        return ComparisonResult(
            runtime_a=name_a,
            runtime_b=name_b,
            states_match=match,
            order_count_match=getattr(state_a, 'orders_created', 0) == getattr(state_b, 'orders_created', 0),
            fill_count_match=getattr(state_a, 'orders_filled', 0) == getattr(state_b, 'orders_filled', 0),
            capital_diff=capital_diff,
            pnl_diff=pnl_diff,
            differences=differences,
        )
    
    def _compare_runtime_state_objects(
        self,
        state_a: Any,
        state_b: Any,
        tolerance: float = 1e-6,
    ) -> bool:
        """比较两个运行时状态对象"""
        if not hasattr(state_a, 'to_dict') or not hasattr(state_b, 'to_dict'):
            return state_a == state_b
        
        dict_a = state_a.to_dict()
        dict_b = state_b.to_dict()
        
        return self._dict_approx_equal(dict_a, dict_b, tolerance)
    
    def _dict_approx_equal(
        self,
        a: Any,
        b: Any,
        tolerance: float,
    ) -> bool:
        """近似相等的字典比较"""
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
        """获取测试历史"""
        return self._test_history.copy()
    
    def get_latest_report(self) -> Optional[TestReport]:
        """获取最新测试报告"""
        return self._test_history[-1] if self._test_history else None
    
    def get_summary(self) -> Dict[str, Any]:
        """获取测试摘要"""
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
    """获取一致性测试器实例"""
    global _tester
    if _tester is None:
        _tester = ConsistencyTester()
    return _tester
