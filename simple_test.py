"""
简单测试脚本，验证 P0-1 和 P0-2 功能
"""

import sys
import os

# 确保能导入 backend 模块
backend_path = os.path.join(os.path.dirname(__file__), 'backend')
sys.path.insert(0, backend_path)

print("=" * 60)
print("P0-1 & P0-2: Event Protocol & Immutable Event - 测试")
print("=" * 60)

try:
    # 测试导入
    print("\n1. 测试模块导入...")
    from domain.event.protocol import (
        FrozenDict,
        EventSource,
        ImmutableEvent,
        ImmutableEventBuilder,
        create_event,
        verify_event,
    )
    print("   ✓ 导入成功")
    
    # 测试 FrozenDict
    print("\n2. 测试 FrozenDict...")
    fd = FrozenDict({"a": 1, "b": 2})
    assert fd["a"] == 1
    assert fd.get("b") == 2
    print("   ✓ FrozenDict 工作正常")
    
    # 测试 ImmutableEvent 创建
    print("\n3. 测试 ImmutableEvent 创建...")
    import dataclasses
    
    event = create_event(
        event_type="candle",
        symbol="BTCUSDT",
        exchange="binance",
        event_time_ms=1000,
        payload={"open": 10000, "close": 10100},
    )
    assert event.event_id == "candle_BTCUSDT_1000"
    assert event.event_type == "candle"
    assert event.available_time_ms == 1000
    print("   ✓ ImmutableEvent 创建成功")
    
    # 测试时间语义验证
    print("\n4. 测试时间语义验证...")
    # 正常情况
    event = create_event(
        event_type="candle",
        symbol="BTCUSDT",
        exchange="binance",
        event_time_ms=1000,
        available_time_ms=1500,
        processing_time_ms=2000,
        payload={},
    )
    
    # 测试约束1: event_time <= available_time
    try:
        create_event(
            event_type="candle",
            symbol="BTCUSDT",
            exchange="binance",
            event_time_ms=2000,
            available_time_ms=1000,
            payload={},
        )
        assert False, "应该抛出异常"
    except ValueError as e:
        print(f"   ✓ 约束1 正确: {e}")
    
    # 测试约束2: available_time <= processing_time
    try:
        create_event(
            event_type="candle",
            symbol="BTCUSDT",
            exchange="binance",
            event_time_ms=1000,
            available_time_ms=2000,
            processing_time_ms=1500,
            payload={},
        )
        assert False, "应该抛出异常"
    except ValueError as e:
        print(f"   ✓ 约束2 正确: {e}")
    
    # 测试真正不可变
    print("\n5. 测试真正不可变...")
    event = create_event(
        event_type="candle",
        symbol="BTCUSDT",
        exchange="binance",
        event_time_ms=1000,
        payload={},
    )
    
    try:
        event.event_time_ms = 2000
        assert False, "应该抛出 FrozenInstanceError"
    except dataclasses.FrozenInstanceError:
        print("   ✓ 事件真正不可变")
    
    # 测试完整性验证
    print("\n6. 测试完整性验证...")
    event = create_event(
        event_type="candle",
        symbol="BTCUSDT",
        exchange="binance",
        event_time_ms=1000,
        payload={},
    )
    assert event.verify_integrity() is True
    print("   ✓ 完整性验证通过")
    
    # 测试特征可用性检查
    print("\n7. 测试特征可用性检查...")
    event = create_event(
        event_type="candle",
        symbol="BTCUSDT",
        exchange="binance",
        event_time_ms=1000,
        available_time_ms=1500,
        payload={},
    )
    assert event.is_available_at(1000) is False
    assert event.is_available_at(1500) is True
    print("   ✓ 可用性检查工作正常")
    
    print("\n" + "=" * 60)
    print("✅ 所有 P0-1 & P0-2 测试通过!")
    print("=" * 60)
    
    # 演示示例
    print("\n" + "=" * 60)
    print("示例: 使用 ImmutableEvent")
    print("=" * 60)
    
    event = create_event(
        event_type="candle",
        symbol="BTCUSDT",
        exchange="binance",
        event_time_ms=1716768000000,
        available_time_ms=1716768001000,
        processing_time_ms=1716768002000,
        payload={"open": 60000, "high": 60500, "low": 59800, "close": 60200},
        source=EventSource.REPLAY,
    )
    
    print(f"\n创建的事件:")
    print(f"  event_id: {event.event_id}")
    print(f"  event_time_ms: {event.event_time_ms}")
    print(f"  available_time_ms: {event.available_time_ms}")
    print(f"  processing_time_ms: {event.processing_time_ms}")
    print(f"  verification_hash: {event.verification_hash[:16]}...")
    print(f"  完整性验证: {event.verify_integrity()}")
    
    print(f"\n可用性检查:")
    print(f"  在 1716768000500 时可用? {event.is_available_at(1716768000500)}")
    print(f"  在 1716768001000 时可用? {event.is_available_at(1716768001000)}")
    print(f"  在 1716768002000 时可用? {event.is_available_at(1716768002000)}")
    
except Exception as e:
    print(f"\n❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()
