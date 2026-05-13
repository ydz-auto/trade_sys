"""
Verification Module - 验证模块

提供系统一致性验证能力：
1. Determinism Verification - 确定性验证
2. Consistency Testing Framework - 一致性测试框架
"""

from .determinism import (
    DeterminismVerifier,
    VerificationResult,
    VerificationStatus,
    StateSnapshot,
    RunResult,
    get_determinism_verifier,
)

from .consistency import (
    ConsistencyTester,
    TestCase,
    TestReport,
    TestType,
    ComparisonResult,
    get_consistency_tester,
)

__all__ = [
    "DeterminismVerifier",
    "VerificationResult",
    "VerificationStatus",
    "StateSnapshot",
    "RunResult",
    "get_determinism_verifier",
    "ConsistencyTester",
    "TestCase",
    "TestReport",
    "TestType",
    "ComparisonResult",
    "get_consistency_tester",
]
