"""
P0-1 & P0-2 测试：Event Protocol & Immutable Event

验证：
1. 三种时间语义正确工作
2. Immutable Event 真正不可变
3. 事件完整性验证
4. 特征可用性检查
"""

import pytest
import time
import dataclasses

from domain.event.protocol import (
    FrozenDict,
    EventSource,
    ImmutableEvent,
    ImmutableEventBuilder,
    create_event,
    verify_event,
)


class TestFrozenDict:
    """测试不可变字典"""

    def test_frozen_dict_basic(self):
        """基本功能测试"""
        data = {"a": 1, "b": 2}
        fd = FrozenDict(data)

        assert fd["a"] == 1
        assert fd.get("b") == 2
        assert "a" in fd
        assert list(fd.keys()) == ["a", "b"]
        assert list(fd.values()) == [1, 2]

    def test_frozen_dict_immutable(self):
        """验证不可变 - 应该无法修改"""
        fd = FrozenDict({"a": 1})

        # 尝试修改应该失败（FrozenDict 没有提供修改方法）
        with pytest.raises(Exception):
            fd["a"] = 2  # type: ignore

    def test_frozen_dict_equality(self):
        """相等性测试"""
        fd1 = FrozenDict({"a": 1, "b": 2})
        fd2 = FrozenDict({"a": 1, "b": 2})
        fd3 = FrozenDict({"a": 1, "b": 3})

        assert fd1 == fd2
        assert fd1 != fd3

    def test_frozen_dict_hash(self):
        """哈希测试"""
        fd1 = FrozenDict({"a": 1, "b": 2})
        fd2 = FrozenDict({"a": 1, "b": 2})

        assert hash(fd1) == hash(fd2)


class TestImmutableEvent:
    """测试不可变事件"""

    def test_create_event_basic(self):
        """基本创建测试"""
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
        assert event.available_time_ms == 1000  # 默认值
        assert event.processing_time_ms == 1000  # 默认值

    def test_create_event_with_available_time(self):
        """带可用时间创建"""
        event = create_event(
            event_type="candle",
            symbol="BTCUSDT",
            exchange="binance",
            event_time_ms=1000,
            available_time_ms=1500,
            payload={"open": 10000, "close": 10100},
        )

        assert event.event_time_ms == 1000
        assert event.available_time_ms == 1500
        assert event.processing_time_ms == 1500

    def test_create_event_full(self):
        """完整时间语义"""
        event = create_event(
            event_type="candle",
            symbol="BTCUSDT",
            exchange="binance",
            event_time_ms=1000,
            available_time_ms=1500,
            processing_time_ms=2000,
            payload={"open": 10000, "close": 10100},
        )

        assert event.event_time_ms == 1000
        assert event.available_time_ms == 1500
        assert event.processing_time_ms == 2000

    def test_time_semantics_validation(self):
        """P0-1: 时间语义验证"""
        # 正常情况应该成功
        event = create_event(
            event_type="candle",
            symbol="BTCUSDT",
            exchange="binance",
            event_time_ms=1000,
            available_time_ms=1500,
            processing_time_ms=2000,
            payload={},
        )

        # 违反 event_time <= available_time
        with pytest.raises(ValueError, match="event_time_ms"):
            create_event(
                event_type="candle",
                symbol="BTCUSDT",
                exchange="binance",
                event_time_ms=2000,
                available_time_ms=1000,
                payload={},
            )

        # 违反 available_time <= processing_time
        with pytest.raises(ValueError, match="available_time_ms"):
            create_event(
                event_type="candle",
                symbol="BTCUSDT",
                exchange="binance",
                event_time_ms=1000,
                available_time_ms=2000,
                processing_time_ms=1500,
                payload={},
            )

    def test_immutable_event_really_immutable(self):
        """P0-2: 验证事件真正不可变"""
        event = create_event(
            event_type="candle",
            symbol="BTCUSDT",
            exchange="binance",
            event_time_ms=1000,
            payload={},
        )

        # 尝试修改字段应该失败
        with pytest.raises(dataclasses.FrozenInstanceError):
            event.event_time_ms = 2000

        with pytest.raises(dataclasses.FrozenInstanceError):
            event.payload = FrozenDict({"new": "data"})

    def test_event_integrity_verification(self):
        """完整性验证"""
        event = create_event(
            event_type="candle",
            symbol="BTCUSDT",
            exchange="binance",
            event_time_ms=1000,
            payload={},
        )

        # 原始事件应该通过验证
        assert event.verify_integrity() is True
        is_valid, issues = verify_event(event)
        assert is_valid is True
        assert len(issues) == 0

    def test_is_available_at(self):
        """P0-3: 特征可用性检查"""
        event = create_event(
            event_type="candle",
            symbol="BTCUSDT",
            exchange="binance",
            event_time_ms=1000,
            available_time_ms=1500,
            payload={},
        )

        # clock_time < available_time - 不可用
        assert event.is_available_at(1000) is False
        assert event.is_available_at(1499) is False

        # clock_time == available_time - 可用
        assert event.is_available_at(1500) is True

        # clock_time > available_time - 可用
        assert event.is_available_at(2000) is True


class TestEventBuilder:
    """测试事件构建器"""

    def test_builder_basic(self):
        """基本构建"""
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
        assert event.event_type == "candle"

    def test_builder_available_after(self):
        """测试 available_after"""
        builder = ImmutableEventBuilder()
        event = (
            builder
            .event_id("test_123")
            .event_type("candle")
            .symbol("BTCUSDT")
            .exchange("binance")
            .event_time_ms(1000)
            .available_after_ms(500)  # available_time = 1000 + 500 = 1500
            .payload({"open": 10000})
            .build()
        )

        assert event.event_time_ms == 1000
        assert event.available_time_ms == 1500


class TestVerifyEvent:
    """测试事件验证"""

    def test_verify_valid_event(self):
        """验证有效事件"""
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


# 运行测试
if __name__ == "__main__":
    import dataclasses

    print("=" * 60)
    print("P0-1 & P0-2: Event Protocol & Immutable Event - 测试")
    print("=" * 60)

    # 测试 1: FrozenDict
    print("\n1. 测试 FrozenDict...")
    fd_test = TestFrozenDict()
    fd_test.test_frozen_dict_basic()
    fd_test.test_frozen_dict_equality()
    fd_test.test_frozen_dict_hash()
    print("   ✓ FrozenDict 测试通过")

    # 测试 2: ImmutableEvent 基本创建
    print("\n2. 测试 ImmutableEvent 创建...")
    event_test = TestImmutableEvent()
    event_test.test_create_event_basic()
    event_test.test_create_event_with_available_time()
    event_test.test_create_event_full()
    print("   ✓ ImmutableEvent 创建测试通过")

    # 测试 3: 时间语义验证
    print("\n3. 测试时间语义验证...")
    event_test.test_time_semantics_validation()
    print("   ✓ 时间语义验证测试通过")

    # 测试 4: 真正不可变
    print("\n4. 测试真正不可变...")
    event_test.test_immutable_event_really_immutable()
    print("   ✓ 不可变测试通过")

    # 测试 5: 完整性验证
    print("\n5. 测试完整性验证...")
    event_test.test_event_integrity_verification()
    print("   ✓ 完整性验证测试通过")

    # 测试 6: 特征可用性检查
    print("\n6. 测试特征可用性检查...")
    event_test.test_is_available_at()
    print("   ✓ 可用性检查测试通过")

    # 测试 7: Event Builder
    print("\n7. 测试 Event Builder...")
    builder_test = TestEventBuilder()
    builder_test.test_builder_basic()
    builder_test.test_builder_available_after()
    print("   ✓ Builder 测试通过")

    # 测试 8: 事件验证
    print("\n8. 测试事件验证...")
    verify_test = TestVerifyEvent()
    verify_test.test_verify_valid_event()
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
        available_time_ms=1716768001000,  # 延迟 1 秒
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
