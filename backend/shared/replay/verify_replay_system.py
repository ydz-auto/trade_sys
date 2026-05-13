"""
Replay/Rebuild System Verification Script
验证回放重建系统的核心功能
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.replay import (
    ReplayOrchestrator,
    get_replay_orchestrator,
    ReplayStatus,
    RebuildStatus,
    EventType,
    ReplayTask,
    RebuildTask,
)
from shared.contracts import Timeframe, Candle


async def verify_replay_system():
    """验证回放系统"""
    print("=" * 60)
    print("Replay/Rebuild System Verification")
    print("=" * 60)
    
    orchestrator = await get_replay_orchestrator()
    
    print("\n[1] Testing ReplayOrchestrator initialization...")
    status = await orchestrator.get_status()
    print(f"    Status: {status}")
    
    print("\n[2] Testing ReplayTask creation...")
    end_time = int(datetime.now().timestamp() * 1000)
    start_time = int((datetime.now() - timedelta(hours=1)).timestamp() * 1000)
    
    replay_task = await orchestrator.create_replay_task(
        exchange="binance",
        symbol="BTCUSDT",
        timeframe="1m",
        start_time=start_time,
        end_time=end_time,
    )
    print(f"    Created replay task: {replay_task.task_id}")
    print(f"    Task status: {replay_task.status.value}")
    
    print("\n[3] Testing RebuildTask creation...")
    rebuild_task = await orchestrator.create_rebuild_task(
        exchange="binance",
        symbol="BTCUSDT",
        timeframe="5m",
        start_time=start_time,
        end_time=end_time,
        strategy="rebuild",
    )
    print(f"    Created rebuild task: {rebuild_task.task_id}")
    print(f"    Task status: {rebuild_task.status.value}")
    
    print("\n[4] Testing task listing...")
    replay_tasks = await orchestrator.list_replay_tasks()
    rebuild_tasks = await orchestrator.list_rebuild_tasks()
    print(f"    Replay tasks: {len(replay_tasks)}")
    print(f"    Rebuild tasks: {len(rebuild_tasks)}")
    
    print("\n[5] Testing statistics...")
    replay_stats = orchestrator.get_replay_stats()
    rebuild_stats = orchestrator.get_rebuild_stats()
    print(f"    Replay stats: {replay_stats.to_dict()}")
    print(f"    Rebuild stats: {rebuild_stats.to_dict()}")
    
    print("\n[6] Testing task cancellation...")
    cancelled = await orchestrator.cancel_replay(replay_task.task_id)
    print(f"    Cancelled replay task: {cancelled}")
    
    cancelled = await orchestrator.cancel_rebuild(rebuild_task.task_id)
    print(f"    Cancelled rebuild task: {cancelled}")
    
    print("\n[7] Verifying task states after cancellation...")
    final_replay = await orchestrator.get_replay_task(replay_task.task_id)
    final_rebuild = await orchestrator.get_rebuild_task(rebuild_task.task_id)
    
    if final_replay:
        print(f"    Final replay status: {final_replay.status.value}")
    if final_rebuild:
        print(f"    Final rebuild status: {final_rebuild.status.value}")
    
    print("\n" + "=" * 60)
    print("✅ Replay/Rebuild System Verification Complete!")
    print("=" * 60)
    
    await orchestrator.shutdown()
    return True


async def verify_models():
    """验证数据模型"""
    print("\n[Model Verification]")
    
    from shared.replay.models import (
        EventRecord, EventType, ReplayCheckpoint,
        ReplayTask, RebuildTask,
    )
    
    event = EventRecord(
        event_id="test_001",
        event_type=EventType.CANDLE_1M,
        exchange="binance",
        symbol="BTCUSDT",
        timestamp=1700000000000,
        data={"open": 50000.0, "close": 50100.0},
    )
    print(f"  EventRecord.to_dict(): {event.to_dict()}")
    
    checkpoint = ReplayCheckpoint(
        checkpoint_id="cp_001",
        replay_id="replay_001",
        exchange="binance",
        symbol="BTCUSDT",
        timeframe="1m",
        last_timestamp=1700000000000,
        last_sequence=100,
        processed_count=1000,
    )
    print(f"  ReplayCheckpoint.to_dict(): {checkpoint.to_dict()}")
    
    print("  ✅ Models verified successfully!")
    return True


async def main():
    """主函数"""
    try:
        await verify_models()
        await verify_replay_system()
    except Exception as e:
        print(f"\n❌ Verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
