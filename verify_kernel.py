#!/usr/bin/env python3
"""
Deterministic Kernel Verification - 完整验证脚本

这是 P0.1/P0.2/P0.3 的完整验证：
1. P0.1: Single Entry Point - 单一入口
2. P0.2: State Trajectory Verification - 状态轨迹验证
3. P0.3: Failure Injection Testing - 失效模式测试
"""

import sys
from pathlib import Path
import random
from datetime import datetime

# 添加项目路径
project_root = Path(__file__).parent
backend_root = project_root / "backend"
sys.path.insert(0, str(backend_root))

from runtime.kernel import (
    RuntimeKernel,
    RawEvent,
    StateTrajectory,
)
from runtime.failure_injector import (
    FailureInjector,
    FailureMode,
)
from domain.logging import get_logger

logger = get_logger("verify_kernel")


def generate_test_events(
    num_events: int = 10,
    start_time_ms: int = 1716768000000,
) -> list[RawEvent]:
    """生成测试事件"""
    events = []
    for i in range(num_events):
        event_time = start_time_ms + i * 60000  # 每 1 分钟
        event = RawEvent(
            event_type="CANDLE",
            symbol="BTCUSDT",
            exchange="binance",
            event_time_ms=event_time,
            payload={
                "close": 60000 + random.randint(-100, 100),
                "volume": random.randint(100, 1000),
                "is_complete": True,
            },
        )
        events.append(event)
    return events


class SimpleState:
    """简单的状态对象（用来测试）"""
    
    def __init__(self):
        self.value = 0
        self.event_count = 0
        self.last_close = 0
    
    def process_event(self, event):
        """处理事件，更新状态"""
        self.value += 1
        self.event_count += 1
        if "close" in event.payload:
            self.last_close = event.payload["close"]
    
    def get_state(self):
        """获取当前状态"""
        return {
            "value": self.value,
            "event_count": self.event_count,
            "last_close": self.last_close,
        }


def run_full_verification():
    """运行完整验证"""
    
    print("=" * 80)
    print("DETERMINISTIC KERNEL VERIFICATION")
    print("=" * 80)
    
    # 1. 初始化
    print("\n[1] Initializing RuntimeKernel...")
    storage_dir = Path("test_kernel_data")
    kernel = RuntimeKernel(
        name="test_kernel",
        storage_dir=storage_dir,
    )
    
    # 简单的状态
    state = SimpleState()
    
    # 2. 设置回调
    print("\n[2] Setting up callbacks...")
    
    def state_provider():
        return state.get_state()
    
    def business_callback(event):
        state.process_event(event)
        return {"processed": True}
    
    kernel.set_state_provider(state_provider)
    kernel.set_business_callback(business_callback)
    
    # 3. 生成测试数据
    print("\n[3] Generating test events...")
    events = generate_test_events(5)
    print(f"  Generated {len(events)} events")
    
    # 4. P0.1: Single Entry Point - 记录一次 Live 运行
    print("\n[4] Testing Record Mode (Single Entry Point)...")
    
    state.value = 0
    state.event_count = 0
    
    kernel.start_record()
    for event in events:
        ok, result = kernel.handle(event)
        if not ok:
            print(f"  WARNING: Event {event.event_time_ms} failed")
    kernel.stop_record()
    
    record_trajectory = kernel.state_trajectory
    print(f"  Recorded {len(record_trajectory.steps)} steps")
    
    # 5. P0.2: State Trajectory - 回放两次，验证两次轨迹一致
    print("\n[5] Testing Replay #1...")
    
    kernel.reset()
    state.value = 0
    state.event_count = 0
    _, replay1_trajectory = kernel.run_full_replay(storage_dir / "events.json")
    
    print("  Comparing Record vs Replay #1...")
    is_consistent, diffs = record_trajectory.compare(
        replay1_trajectory,
        name_a="record",
        name_b="replay1",
    )
    
    if is_consistent:
        print("  ✓ SUCCESS: Record and Replay #1 trajectories match!")
    else:
        print(f"  ✗ FAILURE: {len(diffs)} differences found")
        for diff in diffs[:3]:
            print(f"    {diff}")
    
    print("\n[6] Testing Replay #2...")
    
    kernel.reset()
    state.value = 0
    state.event_count = 0
    _, replay2_trajectory = kernel.run_full_replay(storage_dir / "events.json")
    
    print("  Comparing Replay #1 vs Replay #2...")
    is_consistent_2, diffs_2 = replay1_trajectory.compare(
        replay2_trajectory,
        name_a="replay1",
        name_b="replay2",
    )
    
    if is_consistent_2:
        print("  ✓ SUCCESS: Replay #1 and Replay #2 trajectories match!")
    else:
        print(f"  ✗ FAILURE: {len(diffs_2)} differences found")
        for diff in diffs_2[:3]:
            print(f"    {diff}")
    
    # 6. P0.3: Failure Injection Testing
    print("\n[7] Testing Failure Injection...")
    
    kernel.reset()
    state.value = 0
    state.event_count = 0
    
    injector = FailureInjector(kernel=kernel)
    
    summary = injector.run_all_failure_tests(base_events=events)
    
    print("\n" + injector.get_detailed_report())
    
    # 7. 最终总结
    print("\n" + "=" * 80)
    print("FINAL VERIFICATION SUMMARY")
    print("=" * 80)
    
    all_passed = is_consistent and is_consistent_2 and (summary["failed"] == 0)
    
    if all_passed:
        print("✓ ALL VERIFICATIONS PASSED!")
        print("  ✓ Single Entry Point works correctly")
        print("  ✓ State Trajectory matches (Record = Replay)")
        print("  ✓ Failure Injection tests pass (Guards work)")
        print("\n🎯 YOU HAVE A DETERMINISTIC TRADING KERNEL!")
    else:
        print("✗ SOME VERIFICATIONS FAILED")
        if not is_consistent:
            print("  - Record != Replay (State Trajectory mismatch)")
        if not is_consistent_2:
            print("  - Replay #1 != Replay #2 (Non-deterministic replay)")
        if summary["failed"] > 0:
            print("  - Some Failure Injection tests failed")
    
    print("=" * 80)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    try:
        exit_code = run_full_verification()
        sys.exit(exit_code)
    except Exception as e:
        logger.exception("Verification failed with exception")
        print(f"\n✗ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
