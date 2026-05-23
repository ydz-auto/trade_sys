#!/usr/bin/env python3
"""
All-in-one test - 独立测试文件
"""

import sys
import json
import hashlib
from dataclasses import dataclass
from typing import Dict, Any, Optional, Callable, List, Tuple
from enum import Enum


# ============================================
# 测试：StateTrajectory
# ============================================

@dataclass
class StateTrajectory:
    """状态轨迹"""
    steps: List[Tuple[int, str, str]] = None  # (seq_num, event_id, hash)
    start_time_ms: int = 0
    end_time_ms: int = 0
    
    def __post_init__(self):
        if self.steps is None:
            self.steps = []
    
    def add_step(
        self,
        sequence_number: int,
        event_id: str,
        state_data: Dict[str, Any],
    ):
        content = json.dumps(state_data, sort_keys=True)
        state_hash = hashlib.sha256(content.encode()).hexdigest()[:32]
        self.steps.append((sequence_number, event_id, state_hash))
    
    def compare(self, other):
        diffs = []
        if len(self.steps) != len(other.steps):
            diffs.append({"category": "count_mismatch"})
        min_steps = min(len(self.steps), len(other.steps))
        for i in range(min_steps):
            s1, e1, h1 = self.steps[i]
            s2, e2, h2 = other.steps[i]
            if s1 != s2:
                diffs.append({"category": "seq_mismatch", "i": i})
            if e1 != e2:
                diffs.append({"category": "event_mismatch", "i": i})
            if h1 != h2:
                diffs.append({"category": "hash_mismatch", "i": i})
        return len(diffs) == 0, diffs


# ============================================
# 测试：RawEvent
# ============================================

@dataclass
class RawEvent:
    event_type: str
    symbol: str
    exchange: str
    event_time_ms: int
    payload: Dict[str, Any]


# ============================================
# 运行测试
# ============================================

def main():
    print("=" * 60)
    print("ALL-IN-ONE TEST")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    # 1. Test StateTrajectory
    print("\n[1] Testing StateTrajectory...")
    t1 = StateTrajectory()
    t1.add_step(1, "e1", {"x": 1})
    t1.add_step(2, "e2", {"x": 2})
    
    t2 = StateTrajectory()
    t2.add_step(1, "e1", {"x": 1})
    t2.add_step(2, "e2", {"x": 2})
    
    ok, diff = t1.compare(t2)
    if ok:
        print("  ✓ PASSED: identical trajectories match")
        passed +=1
    else:
        print("  ✗ FAILED: identical trajectories didn't match")
        failed +=1
    
    # 2. Test RawEvent
    print("\n[2] Testing RawEvent...")
    e = RawEvent(
        event_type="CANDLE",
        symbol="BTCUSDT",
        exchange="binance",
        event_time_ms=1716768000000,
        payload={"close": 60000},
    )
    print(f"  ✓ PASSED: created {e.event_type} event for {e.symbol}")
    passed +=1
    
    # 3. Summary
    print("\n" + "=" * 60)
    if failed == 0:
        print(f"✓ ALL {passed} TESTS PASSED!")
    else:
        print(f"✗ {failed} test(s) failed")
    print("=" * 60)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
