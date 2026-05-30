"""
直接运行 P0-1 & P0-2 测试
"""

import sys
import os

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

import dataclasses

from domain.event.protocol import (
    FrozenDict,
    EventSource,
    ImmutableEvent,
    ImmutableEventBuilder,
    create_event,
    verify_event,
)


def run_tests():
    print("=" * 60)
    print("P0-1 & P0-2: Event Protocol & Immutable Event - 测试")
    print("=" * 60)
    
    # 测试 1: FrozenDict
    print("\n1. 测试 FrozenDict...")
    
    # FrozenDict 基本功能
    data = {"a": 1, "b": 2}
    fd = FrozenDict(data)
    assert fd["a"] == 1
    assert fd.get("b") == 2
    assert "a" in fd
    assert list(fd.keys()) == ["a", "b"]
    
    # FrozenDict 相等性
    fd1 = FrozenDict({"a": 1, "b": 2})
    fd2 = FrozenDict({"a": 1, "b": 2})
    fd3 = FrozenDict({"a": 1, "b": 3})
    assert fd1 == fd2
    assert fd1 != fd3
    
    print("   ✓ FrozenDict 测试通过")
    
    # 测试 2: ImmutableEvent 基本创建
    print("\n2. 测试 ImmutableEvent 创建...")
    
    event = create_event(
        event_type="candle",
        symbol="BTCUSDT",
        exchange="binance",
        event_time_ms=1000,
        payload={"open": 10000, "close": 10100},
    )
    
    assert event.event_id == "candle_BTCUSDT_1000"
    assert event.event_type == "candle"
    assert event.symbol == "BTCUSDT"
    assert event.exchange == "binance"
    assert event.event_time_ms == 1000
    
    print("   ✓ ImmutableEvent 创建测试通过")
    
    # 测试 3: 时间语义验证
    print("\n3. 测试时间语义验证...")
    
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
    
    # 测试违反约束的情况
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
        assert "event_time_ms" in str(e)
    
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
        assert "available_time_ms" in str(e)
    
    print("   ✓ 时间语义验证测试通过")
    
    # 测试 4: 真正不可变
    print("\n4. 测试真正不可变...")
    
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
        pass
    
    print("   ✓ 不可变测试通过")
    
    # 测试 5: 完整性验证
    print("\n5. 测试完整性验证...")
    
    event = create_event(
        event_type="candle",
        symbol="BTCUSDT",
        exchange="binance",
        event_time_ms=1000,
        payload={},
    )
    
    assert event.verify_integrity() is True
    is_valid, issues = verify_event(event)
    assert is_valid is True
    assert len(issues) == 0
    
    print("   ✓ 完整性验证测试通过")
    
    # 测试 6: 特征可用性检查
    print("\n6. 测试特征可用性检查...")
    
    event = create_event(
        event_type="candle",
        symbol="BTCUSDT",
        exchange="binance",
        event_time_ms=1000,
        available_time_ms=1500,
        payload={},
    )
    
    assert event.is_available_at(1000) is False
    assert event.is_available_at(1499) is False
    assert event.is_available_at(1500) is True
    assert event.is_available_at(2000) is True
    
    print("   ✓ 可用性检查测试通过")
    
    # 测试 7: Event Builder
    print("\n7. 测试 Event Builder...")
    
    builder = ImmutableEventBuilder()
    event = (
        builder
        .event_id("test_123")
        .event_type("candle")
        .symbol("BTCUSDT")
        .exchange("binance")
        .event_time_ms(1000)
        .payload({"open": 10000})
        .build()
    )
    
    assert event.event_id == "test_123"
    
    # 测试 available_after
    builder = ImmutableEventBuilder()
    event = (
        builder
        .event_id("test_456")
        .event_type("candle")
        .symbol("BTCUSDT")
        .exchange("binance")
        .event_time_ms(1000)
        .available_after_ms(500)
        .payload({"open": 10000})
        .build()
    )
    
    assert event.event_time_ms == 1000
    assert event.available_time_ms == 1500
    
    print("   ✓ Builder 测试通过")
    
    # 测试 8: 事件验证
    print("\n8. 测试事件验证...")
    
    event = create_event(
        event_type="candle",
        symbol="BTCUSDT",
        exchange="binance",
        event_time_ms=1000,
        available_time_ms=1500,
        processing_time_ms=2000,
        payload={},
    )
    
    is_valid, issues = verify_event(event)
    assert is_valid is True
    assert len(issues) == 0
    
    print("   ✓ 事件验证测试通过")
    
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


if __name__ == "__main__":
    run_tests()
