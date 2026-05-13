"""
Determinism Verification - 确定性验证系统

验证系统是否满足：
- 同输入 = 同输出
- 同输入 = 同状态演化
- 同输入 = 同执行结果

这是专业量化系统的核心要求。
"""

import asyncio
import hashlib
import json
from typing import Dict, List, Optional, Any, Callable, Awaitable, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import uuid

from infrastructure.logging import get_logger

logger = get_logger("infrastructure.verification.determinism")


class VerificationStatus(str, Enum):
    """验证状态"""
    PASSED = "passed"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"
    SKIPPED = "skipped"


@dataclass
class VerificationResult:
    """验证结果"""
    verification_id: str
    test_name: str
    status: VerificationStatus
    
    expected: Any
    actual: Any
    
    differences: List[Dict[str, Any]] = field(default_factory=list)
    
    execution_time_ms: float = 0.0
    
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_passed(self) -> bool:
        return self.status == VerificationStatus.PASSED
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "verification_id": self.verification_id,
            "test_name": self.test_name,
            "status": self.status.value,
            "expected": str(self.expected)[:1000] if isinstance(self.expected, (dict, list)) else self.expected,
            "actual": str(self.actual)[:1000] if isinstance(self.actual, (dict, list)) else self.actual,
            "differences": self.differences,
            "execution_time_ms": self.execution_time_ms,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class StateSnapshot:
    """状态快照"""
    state_id: str
    timestamp: datetime
    
    event_count: int
    sequence: int
    
    state_hash: str
    detailed_state: Dict[str, Any]
    
    def compute_hash(self) -> str:
        state_str = json.dumps(self.detailed_state, sort_keys=True, default=str)
        return hashlib.sha256(state_str.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "state_id": self.state_id,
            "timestamp": self.timestamp.isoformat(),
            "event_count": self.event_count,
            "sequence": self.sequence,
            "state_hash": self.state_hash,
        }


@dataclass
class RunResult:
    """运行结果"""
    run_id: str
    run_number: int
    
    events: List[Dict[str, Any]]
    final_state: Dict[str, Any]
    
    state_hash: str
    execution_time_ms: float
    
    events_hash: str
    order_count: int
    fill_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "run_number": self.run_number,
            "state_hash": self.state_hash,
            "execution_time_ms": self.execution_time_ms,
            "events_hash": self.events_hash,
            "order_count": self.order_count,
            "fill_count": self.fill_count,
            "event_count": len(self.events),
        }


class DeterminismVerifier:
    """确定性验证器
    
    验证系统是否满足确定性要求
    """
    
    def __init__(self):
        self._verification_history: List[VerificationResult] = []
        self._state_comparators: Dict[str, Callable] = {}
    
    def register_comparator(
        self,
        state_type: str,
        comparator: Callable[[Any, Any], Tuple[bool, List[Dict[str, Any]]]],
    ) -> None:
        """注册状态比较器"""
        self._state_comparators[state_type] = comparator
    
    async def verify_determinism(
        self,
        test_name: str,
        run_function: Callable[[], Awaitable[RunResult]],
        runs: int = 3,
    ) -> VerificationResult:
        """验证确定性 - 运行多次比较结果"""
        start_time = datetime.utcnow()
        verification_id = f"det_{uuid.uuid4().hex[:12]}"
        
        try:
            results = []
            for i in range(runs):
                result = await run_function()
                results.append(result)
                logger.debug(f"Run {i+1}/{runs}: hash={result.state_hash}")
            
            all_hashes_match = all(
                r.state_hash == results[0].state_hash
                for r in results
            )
            
            all_order_counts_match = all(
                r.order_count == results[0].order_count
                for r in results
            )
            
            all_fill_counts_match = all(
                r.fill_count == results[0].fill_count
                for r in results
            )
            
            differences = []
            if not all_hashes_match:
                differences.append({
                    "type": "state_hash",
                    "message": "State hashes do not match across runs",
                    "hashes": [r.state_hash for r in results],
                })
            
            if not all_order_counts_match:
                differences.append({
                    "type": "order_count",
                    "message": "Order counts do not match across runs",
                    "counts": [r.order_count for r in results],
                })
            
            if not all_fill_counts_match:
                differences.append({
                    "type": "fill_count",
                    "message": "Fill counts do not match across runs",
                    "counts": [r.fill_count for r in results],
                })
            
            is_passed = all_hashes_match and all_order_counts_match and all_fill_counts_match
            
            result = VerificationResult(
                verification_id=verification_id,
                test_name=test_name,
                status=VerificationStatus.PASSED if is_passed else VerificationStatus.FAILED,
                expected=results[0].state_hash,
                actual=[r.state_hash for r in results],
                differences=differences,
                execution_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                metadata={
                    "runs": runs,
                    "results": [r.to_dict() for r in results],
                },
            )
            
            self._verification_history.append(result)
            
            if is_passed:
                logger.info(f"Determinism verification PASSED: {test_name}")
            else:
                logger.error(f"Determinism verification FAILED: {test_name}")
            
            return result
            
        except Exception as e:
            logger.error(f"Determinism verification ERROR: {e}")
            result = VerificationResult(
                verification_id=verification_id,
                test_name=test_name,
                status=VerificationStatus.INCONCLUSIVE,
                expected=None,
                actual=None,
                differences=[{"type": "error", "message": str(e)}],
                execution_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
            )
            self._verification_history.append(result)
            return result
    
    async def verify_state_evolution(
        self,
        test_name: str,
        initial_state: Dict[str, Any],
        events: List[Dict[str, Any]],
        evolve_function: Callable[[Dict, List], Awaitable[Dict]],
        expected_final_state: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        """验证状态演化"""
        start_time = datetime.utcnow()
        verification_id = f"evo_{uuid.uuid4().hex[:12]}"
        
        try:
            final_state = await evolve_function(initial_state, events)
            
            differences = []
            
            if expected_final_state:
                diff = self._compare_states(expected_final_state, final_state)
                differences.extend(diff)
            
            is_passed = len(differences) == 0
            
            result = VerificationResult(
                verification_id=verification_id,
                test_name=test_name,
                status=VerificationStatus.PASSED if is_passed else VerificationStatus.FAILED,
                expected=expected_final_state,
                actual=final_state,
                differences=differences,
                execution_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                metadata={
                    "initial_state_keys": list(initial_state.keys()),
                    "event_count": len(events),
                    "final_state_keys": list(final_state.keys()),
                },
            )
            
            self._verification_history.append(result)
            return result
            
        except Exception as e:
            result = VerificationResult(
                verification_id=verification_id,
                test_name=test_name,
                status=VerificationStatus.INCONCLUSIVE,
                expected=expected_final_state,
                actual=None,
                differences=[{"type": "error", "message": str(e)}],
                execution_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
            )
            self._verification_history.append(result)
            return result
    
    async def verify_snapshot_consistency(
        self,
        test_name: str,
        save_snapshot_function: Callable[[], Awaitable[StateSnapshot]],
        continue_function: Callable[[], Awaitable[None]],
        restore_snapshot_function: Callable[[StateSnapshot], Awaitable[Dict]],
        events_after_save: List[Dict[str, Any]],
        process_events_function: Callable[[List], Awaitable[Dict]],
    ) -> VerificationResult:
        """验证快照一致性"""
        start_time = datetime.utcnow()
        verification_id = f"snap_{uuid.uuid4().hex[:12]}"
        
        try:
            snapshot = await save_snapshot_function()
            
            await continue_function()
            
            state_after_continue = await process_events_function(events_after_save)
            
            restored_state = await restore_snapshot_function(snapshot)
            
            diff = self._compare_states(snapshot.detailed_state, restored_state)
            
            is_passed = len(diff) == 0
            
            result = VerificationResult(
                verification_id=verification_id,
                test_name=test_name,
                status=VerificationStatus.PASSED if is_passed else VerificationStatus.FAILED,
                expected=snapshot.state_hash,
                actual=restored_state.get("_hash", "") if isinstance(restored_state, dict) else "",
                differences=diff,
                execution_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                metadata={
                    "snapshot_hash": snapshot.state_hash,
                    "event_count_after_save": len(events_after_save),
                },
            )
            
            self._verification_history.append(result)
            return result
            
        except Exception as e:
            result = VerificationResult(
                verification_id=verification_id,
                test_name=test_name,
                status=VerificationStatus.INCONCLUSIVE,
                expected=None,
                actual=None,
                differences=[{"type": "error", "message": str(e)}],
                execution_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
            )
            self._verification_history.append(result)
            return result
    
    def _compare_states(
        self,
        expected: Dict[str, Any],
        actual: Dict[str, Any],
        path: str = "",
    ) -> List[Dict[str, Any]]:
        """比较两个状态"""
        differences = []
        
        if type(expected) != type(actual):
            differences.append({
                "type": "type_mismatch",
                "path": path or "root",
                "expected_type": type(expected).__name__,
                "actual_type": type(actual).__name__,
            })
            return differences
        
        if isinstance(expected, dict):
            all_keys = set(expected.keys()) | set(actual.keys())
            for key in all_keys:
                key_path = f"{path}.{key}" if path else key
                
                if key not in expected:
                    differences.append({
                        "type": "missing_key",
                        "path": key_path,
                        "actual_value": actual[key],
                    })
                elif key not in actual:
                    differences.append({
                        "type": "extra_key",
                        "path": key_path,
                        "expected_value": expected[key],
                    })
                else:
                    sub_diff = self._compare_states(expected[key], actual[key], key_path)
                    differences.extend(sub_diff)
        
        elif isinstance(expected, (list, tuple)):
            if len(expected) != len(actual):
                differences.append({
                    "type": "length_mismatch",
                    "path": path,
                    "expected_length": len(expected),
                    "actual_length": len(actual),
                })
            else:
                for i, (e, a) in enumerate(zip(expected, actual)):
                    sub_diff = self._compare_states(e, a, f"{path}[{i}]")
                    differences.extend(sub_diff)
        
        else:
            if expected != actual:
                differences.append({
                    "type": "value_mismatch",
                    "path": path,
                    "expected_value": expected,
                    "actual_value": actual,
                    "difference": float(actual) - float(expected) if isinstance(expected, (int, float)) and isinstance(actual, (int, float)) else None,
                })
        
        return differences
    
    def get_history(self) -> List[VerificationResult]:
        """获取验证历史"""
        return self._verification_history.copy()
    
    def get_summary(self) -> Dict[str, Any]:
        """获取验证摘要"""
        total = len(self._verification_history)
        passed = sum(1 for r in self._verification_history if r.is_passed())
        failed = sum(1 for r in self._verification_history if r.status == VerificationStatus.FAILED)
        inconclusive = sum(1 for r in self._verification_history if r.status == VerificationStatus.INCONCLUSIVE)
        
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "inconclusive": inconclusive,
            "pass_rate": passed / total if total > 0 else 0,
            "last_verification": self._verification_history[-1].to_dict() if self._verification_history else None,
        }


_verifier: Optional[DeterminismVerifier] = None


def get_determinism_verifier() -> DeterminismVerifier:
    """获取确定性验证器实例"""
    global _verifier
    if _verifier is None:
        _verifier = DeterminismVerifier()
    return _verifier
