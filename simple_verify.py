#!/usr/bin/env python3
"""
Simple verification of the kernel components - 简单验证
"""

import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
backend_root = project_root / "backend"
sys.path.insert(0, str(backend_root))


def test_imports():
    """测试导入是否正常"""
    print("Testing imports...")
    try:
        # 导入
        from runtime.kernel import RuntimeKernel, RawEvent
        from runtime.authority import AuthoritySystem, ClockAuthority, ClockMode
        from runtime.guards import GuardSystem
        
        print("✓ Imports OK")
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_state_trajectory():
    """测试 StateTrajectory"""
    print("\nTesting StateTrajectory...")
    try:
        from runtime.kernel import StateTrajectory
        
        trajectory = StateTrajectory()
        
        trajectory.add_step(
            sequence_number=1,
            event_id="test_1",
            state_data={"value": 1},
        )
        trajectory.add_step(
            sequence_number=2,
            event_id="test_2",
            state_data={"value": 2},
        )
        
        trajectory2 = StateTrajectory()
        trajectory2.add_step(
            sequence_number=1,
            event_id="test_1",
            state_data={"value": 1},
        )
        trajectory2.add_step(
            sequence_number=2,
            event_id="test_2",
            state_data={"value": 2},
        )
        
        is_consistent, diffs = trajectory.compare(trajectory2)
        print(f"  Trajectory comparison: {'OK' if is_consistent else 'FAIL'}")
        
        if is_consistent:
            print("✓ StateTrajectory works")
            return True
        else:
            print("✗ StateTrajectory comparison failed")
            return False
            
    except Exception as e:
        print(f"✗ StateTrajectory failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_raw_event():
    """测试 RawEvent"""
    print("\nTesting RawEvent...")
    try:
        from runtime.kernel import RawEvent
        
        event = RawEvent(
            event_type="CANDLE",
            symbol="BTCUSDT",
            exchange="binance",
            event_time_ms=1716768000000,
            payload={"close": 60000},
        )
        
        print(f"  Event: {event.event_type} {event.symbol} @ {event.event_time_ms}")
        print("✓ RawEvent works")
        return True
        
    except Exception as e:
        print(f"✗ RawEvent failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("SIMPLE KERNEL VERIFICATION")
    print("=" * 60)
    
    all_passed = True
    
    if not test_imports():
        all_passed = False
    
    if not test_state_trajectory():
        all_passed = False
    
    if not test_raw_event():
        all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ ALL TESTS PASSED!")
    else:
        print("✗ SOME TESTS FAILED")
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
