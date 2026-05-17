"""
Runtime Governor Tests - 完整测试套件

测试覆盖:
- PriorityEventQueue: 优先级事件队列
- DegradationController: 推送降级控制器
- CircuitBreakerManager: 熔断器管理器
- SubscriptionManager: 订阅管理器
- RuntimeGovernor: 总控制器
"""

import asyncio
import pytest
import time
from datetime import datetime

from infrastructure.runtime.priority_queue import (
    EventPriority,
    PrioritizedEvent,
    PriorityEventQueue,
)
from infrastructure.runtime.degradation import (
    RuntimeMode,
    DegradationConfig,
    DegradationController,
    DEGRADATION_PROFILES,
)
from infrastructure.runtime.circuit_breaker_manager import (
    CircuitState,
    CircuitBreakerConfig,
    CircuitBreaker,
    CircuitBreakerManager,
    CircuitBreakerOpenError,
    get_circuit_breaker_manager,
)
from infrastructure.runtime.subscription_manager import (
    Subscription,
    SubscriptionManager,
    TopicRegistry,
)
from infrastructure.runtime.governor import (
    GovernorState,
    GovernorConfig,
    RuntimeGovernor,
)


class TestPriorityEventQueue:
    """优先级事件队列测试"""

    def test_create_queue(self):
        queue = PriorityEventQueue()
        assert queue.is_empty()
        assert queue.size() == 0

    def test_push_and_pop_event(self):
        queue = PriorityEventQueue()
        
        event = PrioritizedEvent(
            priority=EventPriority.P1_HIGH,
            event_type="test_event",
            payload={"data": "test"},
        )
        
        result = queue.push_nowait(event)
        assert result is True
        assert queue.size() == 1
        
        popped = queue.pop_nowait()
        assert popped is not None
        assert popped.event_type == "test_event"
        assert popped.priority == EventPriority.P1_HIGH

    def test_priority_ordering(self):
        queue = PriorityEventQueue()
        
        low_event = PrioritizedEvent(
            priority=EventPriority.P3_LOW,
            event_type="low",
            payload={},
        )
        high_event = PrioritizedEvent(
            priority=EventPriority.P1_HIGH,
            event_type="high",
            payload={},
        )
        critical_event = PrioritizedEvent(
            priority=EventPriority.P0_CRITICAL,
            event_type="critical",
            payload={},
        )
        
        queue.push_nowait(low_event)
        queue.push_nowait(high_event)
        queue.push_nowait(critical_event)
        
        first = queue.pop_nowait()
        assert first.event_type == "critical"
        
        second = queue.pop_nowait()
        assert second.event_type == "high"
        
        third = queue.pop_nowait()
        assert third.event_type == "low"

    def test_queue_overflow_drop(self):
        queue = PriorityEventQueue(max_size_per_priority=2, total_max_size=10)
        
        for i in range(10):
            event = PrioritizedEvent(
                priority=EventPriority.P2_NORMAL,
                event_type=f"event_{i}",
                payload={},
                drop_on_overload=True,
            )
            queue.push_nowait(event)
        
        overflow_event = PrioritizedEvent(
            priority=EventPriority.P2_NORMAL,
            event_type="overflow",
            payload={},
            drop_on_overload=True,
        )
        result = queue.push_nowait(overflow_event)
        assert result is False

    def test_critical_event_not_dropped(self):
        queue = PriorityEventQueue(max_size_per_priority=1, total_max_size=1)
        
        event1 = PrioritizedEvent(
            priority=EventPriority.P0_CRITICAL,
            event_type="critical1",
            payload={},
            drop_on_overload=False,
        )
        queue.push_nowait(event1)
        
        event2 = PrioritizedEvent(
            priority=EventPriority.P0_CRITICAL,
            event_type="critical2",
            payload={},
            drop_on_overload=False,
        )
        
        with pytest.raises(asyncio.QueueFull):
            queue.push_nowait(event2)

    def test_stats(self):
        queue = PriorityEventQueue()
        
        for i in range(5):
            event = PrioritizedEvent(
                priority=EventPriority.P2_NORMAL,
                event_type=f"event_{i}",
                payload={},
            )
            queue.push_nowait(event)
        
        stats = queue.get_stats()
        assert stats["total_enqueued"] == 5
        assert stats["current_size"] == 5

    @pytest.mark.asyncio
    async def test_async_push_pop(self):
        queue = PriorityEventQueue()
        
        event = PrioritizedEvent(
            priority=EventPriority.P1_HIGH,
            event_type="async_event",
            payload={"async": True},
        )
        
        result = await queue.push(event)
        assert result is True
        
        popped = await queue.pop(timeout=0.1)
        assert popped is not None
        assert popped.event_type == "async_event"


class TestDegradationController:
    """降级控制器测试"""

    def test_create_controller(self):
        controller = DegradationController()
        assert controller.mode == RuntimeMode.NORMAL
        assert controller.config is not None

    def test_mode_profiles(self):
        assert RuntimeMode.NORMAL in DEGRADATION_PROFILES
        assert RuntimeMode.DEGRADED in DEGRADATION_PROFILES
        assert RuntimeMode.CRITICAL in DEGRADATION_PROFILES
        
        normal_config = DEGRADATION_PROFILES[RuntimeMode.NORMAL]
        critical_config = DEGRADATION_PROFILES[RuntimeMode.CRITICAL]
        degraded_config = DEGRADATION_PROFILES[RuntimeMode.DEGRADED]
        
        assert normal_config.factor_interval_ms < critical_config.factor_interval_ms
        assert normal_config.ai_enabled is True
        assert critical_config.ai_enabled is False
        assert degraded_config.tick_interval_ms > normal_config.tick_interval_ms

    def test_should_drop_event(self):
        controller = DegradationController()
        
        controller._current_mode = RuntimeMode.NORMAL
        assert controller.should_drop_event(EventPriority.P0_CRITICAL) is False
        assert controller.should_drop_event(EventPriority.P4_BACKGROUND) is False
        
        controller._current_mode = RuntimeMode.CRITICAL
        assert controller.should_drop_event(EventPriority.P0_CRITICAL) is False
        assert controller.should_drop_event(EventPriority.P1_HIGH) is False
        assert controller.should_drop_event(EventPriority.P2_NORMAL) is True
        assert controller.should_drop_event(EventPriority.P4_BACKGROUND) is True

    def test_should_process_event(self):
        controller = DegradationController()
        
        controller._current_mode = RuntimeMode.NORMAL
        assert controller.should_process_event("ai_summary") is True
        assert controller.should_process_event("replay") is True
        
        controller._current_mode = RuntimeMode.SAFE_MODE
        controller._config = DEGRADATION_PROFILES[RuntimeMode.SAFE_MODE]
        assert controller.should_process_event("ai_summary") is False
        assert controller.should_process_event("replay") is False
        assert controller.should_process_event("tick") is True

    def test_auto_adjust_mode(self):
        controller = DegradationController(auto_adjust=True)
        
        controller.update_load_metrics_sync({
            "cpu": 50,
            "queue_lag": 100,
        })
        assert controller.mode == RuntimeMode.NORMAL
        
        controller._last_mode_change = 0
        controller.update_load_metrics_sync({
            "cpu": 95,
            "queue_lag": 15000,
        })
        assert controller.mode == RuntimeMode.CRITICAL

    def test_get_interval_ms(self):
        controller = DegradationController()
        
        controller._current_mode = RuntimeMode.NORMAL
        controller._config = DEGRADATION_PROFILES[RuntimeMode.NORMAL]
        normal_tick = controller.get_interval_ms("tick")
        
        controller._current_mode = RuntimeMode.DEGRADED
        controller._config = DEGRADATION_PROFILES[RuntimeMode.DEGRADED]
        degraded_tick = controller.get_interval_ms("tick")
        
        assert normal_tick < degraded_tick

    @pytest.mark.asyncio
    async def test_set_mode(self):
        controller = DegradationController()
        
        await controller.set_mode(RuntimeMode.DEGRADED, "test")
        assert controller.mode == RuntimeMode.DEGRADED
        
        stats = controller.get_stats()
        assert stats["current_mode"] == "degraded"
        assert len(stats["mode_history"]) > 0


class TestCircuitBreaker:
    """熔断器测试"""

    def test_create_circuit_breaker(self):
        config = CircuitBreakerConfig(
            name="test",
            failure_threshold=3,
            recovery_timeout_ms=1000,
        )
        cb = CircuitBreaker(config)
        
        assert cb.state == CircuitState.CLOSED
        assert cb.is_closed is True
        assert cb.is_open is False

    @pytest.mark.asyncio
    async def test_success_calls(self):
        config = CircuitBreakerConfig(name="test", failure_threshold=3)
        cb = CircuitBreaker(config)
        
        async def success_func():
            return "success"
        
        for _ in range(10):
            result = await cb.call(success_func)
            assert result == "success"
        
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_failure_opens_circuit(self):
        config = CircuitBreakerConfig(
            name="test",
            failure_threshold=2,
            recovery_timeout_ms=10000,
        )
        cb = CircuitBreaker(config)
        
        async def failing_func():
            raise ValueError("test error")
        
        for _ in range(2):
            with pytest.raises(ValueError):
                await cb.call(failing_func)
        
        assert cb.state == CircuitState.OPEN
        
        with pytest.raises(CircuitBreakerOpenError):
            await cb.call(lambda: "test")

    @pytest.mark.asyncio
    async def test_fallback_on_open(self):
        config = CircuitBreakerConfig(
            name="test",
            failure_threshold=1,
            recovery_timeout_ms=10000,
        )
        
        async def fallback():
            return "fallback_result"
        
        cb = CircuitBreaker(config, fallback=fallback)
        
        async def failing_func():
            raise ValueError("test error")
        
        with pytest.raises(ValueError):
            await cb.call(failing_func)
        
        assert cb.state == CircuitState.OPEN
        
        result = await cb.call(lambda: "normal")
        assert result == "fallback_result"

    @pytest.mark.asyncio
    async def test_half_open_recovery(self):
        config = CircuitBreakerConfig(
            name="test",
            failure_threshold=1,
            recovery_timeout_ms=100,
            success_threshold=1,
        )
        cb = CircuitBreaker(config)
        
        async def failing_func():
            raise ValueError("test error")
        
        with pytest.raises(ValueError):
            await cb.call(failing_func)
        
        assert cb.state == CircuitState.OPEN
        
        await asyncio.sleep(0.15)
        
        async def success_func():
            return "recovered"
        
        result = await cb.call(success_func)
        assert result == "recovered"
        assert cb.state == CircuitState.CLOSED

    def test_reset(self):
        config = CircuitBreakerConfig(name="test", failure_threshold=1)
        cb = CircuitBreaker(config)
        
        cb.force_open()
        assert cb.state == CircuitState.OPEN
        
        cb.reset()
        assert cb.state == CircuitState.CLOSED


class TestCircuitBreakerManager:
    """熔断器管理器测试"""

    def test_create_manager(self):
        manager = CircuitBreakerManager()
        
        assert "ai_runtime" in manager._circuits
        assert "exchange_api" in manager._circuits
        assert "database" in manager._circuits

    def test_get_circuit(self):
        manager = CircuitBreakerManager()
        
        cb = manager.get("ai_runtime")
        assert cb is not None
        assert cb.config.name == "ai_runtime"
        
        custom_cb = manager.get("custom_circuit")
        assert custom_cb is not None

    @pytest.mark.asyncio
    async def test_call_through_manager(self):
        manager = CircuitBreakerManager()
        
        async def test_func():
            return "result"
        
        result = await manager.call("ai_runtime", test_func)
        assert result == "result"

    def test_get_all_stats(self):
        manager = CircuitBreakerManager()
        
        stats = manager.get_all_stats()
        assert "ai_runtime" in stats
        assert "exchange_api" in stats

    def test_is_healthy(self):
        manager = CircuitBreakerManager()
        
        assert manager.is_healthy() is True
        
        manager.force_open("exchange_api")
        assert manager.is_healthy() is False
        
        manager.reset("exchange_api")
        assert manager.is_healthy() is True


class TestSubscriptionManager:
    """订阅管理器测试"""

    def test_create_manager(self):
        manager = SubscriptionManager()
        assert manager.get_stats()["total_subscriptions"] == 0

    def test_subscribe(self):
        manager = SubscriptionManager()
        
        sub = Subscription(
            topic="channel:dashboard",
            subscriber_id="client_1",
            priority=EventPriority.P2_NORMAL,
        )
        
        result = manager.subscribe_sync(sub)
        assert result is True
        assert manager.is_subscribed("channel:dashboard", "client_1")
        assert manager.has_subscribers("channel:dashboard")

    def test_unsubscribe(self):
        manager = SubscriptionManager()
        
        sub = Subscription(
            topic="channel:dashboard",
            subscriber_id="client_1",
        )
        manager.subscribe_sync(sub)
        
        removed = manager.unsubscribe_sync("client_1", "channel:dashboard")
        assert removed == 1
        assert not manager.is_subscribed("channel:dashboard", "client_1")

    def test_disconnect_client(self):
        manager = SubscriptionManager()
        
        for topic in ["channel:dashboard", "channel:risk", "channel:signal"]:
            sub = Subscription(
                topic=topic,
                subscriber_id="client_1",
            )
            manager.subscribe_sync(sub)
        
        removed = manager.unsubscribe_sync("client_1")
        assert removed == 3
        assert len(manager.get_subscriptions("client_1")) == 0

    def test_max_subscriptions_per_client(self):
        manager = SubscriptionManager(max_subscriptions_per_client=3)
        
        for i in range(3):
            sub = Subscription(
                topic=f"channel:topic_{i}",
                subscriber_id="client_1",
            )
            assert manager.subscribe_sync(sub) is True
        
        sub = Subscription(
            topic="channel:topic_4",
            subscriber_id="client_1",
        )
        assert manager.subscribe_sync(sub) is False

    def test_topic_registry(self):
        assert TopicRegistry.ORDER in TopicRegistry.CRITICAL_TOPICS
        assert TopicRegistry.PRICE in TopicRegistry.HIGH_PRIORITY_TOPICS
        assert TopicRegistry.AI in TopicRegistry.LOW_PRIORITY_TOPICS
        
        assert TopicRegistry.get_priority(TopicRegistry.ORDER) == EventPriority.P0_CRITICAL
        assert TopicRegistry.get_priority(TopicRegistry.PRICE) == EventPriority.P1_HIGH

    @pytest.mark.asyncio
    async def test_async_subscribe(self):
        manager = SubscriptionManager()
        
        sub = Subscription(
            topic="channel:dashboard",
            subscriber_id="client_1",
        )
        
        result = await manager.subscribe(sub)
        assert result is True


class TestRuntimeGovernor:
    """总控制器测试"""

    def test_create_governor(self):
        governor = RuntimeGovernor()
        
        assert governor.state == GovernorState.STOPPED
        assert governor.priority_queue is not None
        assert governor.degradation is not None
        assert governor.circuit_breakers is not None
        assert governor.subscriptions is not None

    @pytest.mark.asyncio
    async def test_start_stop(self):
        governor = RuntimeGovernor()
        
        await governor.start()
        assert governor.is_running is True
        assert governor.state == GovernorState.RUNNING
        
        await asyncio.sleep(0.5)
        
        await governor.stop()
        assert governor.is_running is False
        assert governor.state == GovernorState.STOPPED

    @pytest.mark.asyncio
    async def test_push_event(self):
        governor = RuntimeGovernor()
        await governor.start()
        
        event = PrioritizedEvent(
            priority=EventPriority.P1_HIGH,
            event_type="test_event",
            payload={"test": "data"},
        )
        
        result = await governor.push_event(event)
        assert result is True
        
        stats = governor.get_stats()
        assert stats["queue_stats"]["total_enqueued"] >= 1
        
        await governor.stop()

    @pytest.mark.asyncio
    async def test_event_handler(self):
        governor = RuntimeGovernor()
        await governor.start()
        
        processed_events = []
        
        async def handler(event):
            processed_events.append(event)
        
        governor.register_event_handler("test_event", handler)
        
        event = PrioritizedEvent(
            priority=EventPriority.P1_HIGH,
            event_type="test_event",
            payload={"test": "data"},
        )
        
        await governor.push_event(event)
        
        await asyncio.sleep(0.5)
        
        assert len(processed_events) >= 1
        
        governor.unregister_event_handler("test_event")
        
        await governor.stop()

    @pytest.mark.asyncio
    async def test_mode_change(self):
        governor = RuntimeGovernor()
        await governor.start()
        
        await governor.set_mode(RuntimeMode.DEGRADED, "test")
        assert governor.get_mode() == RuntimeMode.DEGRADED
        
        await governor.stop()

    @pytest.mark.asyncio
    async def test_health_check(self):
        governor = RuntimeGovernor()
        await governor.start()
        
        assert governor.is_healthy() is True
        
        governor.circuit_breakers.force_open("exchange_api")
        
        await asyncio.sleep(0.5)
        
        assert governor.is_healthy() is False
        
        governor.circuit_breakers.reset("exchange_api")
        
        await governor.stop()


class TestIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_full_workflow(self):
        governor = RuntimeGovernor()
        await governor.start()
        
        event = PrioritizedEvent(
            priority=EventPriority.P0_CRITICAL,
            event_type="order_filled",
            payload={
                "order_id": "123",
                "symbol": "BTC",
                "quantity": 1.0,
            },
        )
        
        result = await governor.push_event(event)
        assert result is True
        
        sub = Subscription(
            topic=TopicRegistry.ORDER,
            subscriber_id="test_client",
            priority=EventPriority.P0_CRITICAL,
        )
        await governor.subscriptions.subscribe(sub)
        
        assert governor.subscriptions.has_subscribers(TopicRegistry.ORDER)
        
        await governor.set_mode(RuntimeMode.DEGRADED, "test")
        
        low_event = PrioritizedEvent(
            priority=EventPriority.P4_BACKGROUND,
            event_type="replay_tick",
            payload={},
        )
        result = await governor.push_event(low_event)
        assert result is False
        
        stats = governor.get_stats()
        assert stats["degradation_stats"]["current_mode"] == "degraded"
        
        await governor.stop()

    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self):
        governor = RuntimeGovernor()
        await governor.start()
        
        async def failing_api():
            raise Exception("API error")
        
        for _ in range(5):
            try:
                await governor.circuit_breakers.call("exchange_api", failing_api)
            except Exception:
                pass
        
        cb = governor.circuit_breakers.get("exchange_api")
        assert cb.state == CircuitState.OPEN
        
        await governor.force_recovery()
        
        cb = governor.circuit_breakers.get("exchange_api")
        assert cb.state == CircuitState.CLOSED
        
        await governor.stop()

    @pytest.mark.asyncio
    async def test_degradation_under_load(self):
        governor = RuntimeGovernor()
        await governor.start()
        
        for i in range(100):
            event = PrioritizedEvent(
                priority=EventPriority.P2_NORMAL,
                event_type=f"test_event_{i}",
                payload={"index": i},
            )
            await governor.push_event(event)
        
        governor.degradation._last_mode_change = 0
        governor.degradation.update_load_metrics_sync({
            "cpu": 95,
            "queue_lag": 15000,
        })
        
        await asyncio.sleep(0.5)
        
        assert governor.get_mode() == RuntimeMode.CRITICAL
        
        critical_event = PrioritizedEvent(
            priority=EventPriority.P0_CRITICAL,
            event_type="liquidation_warning",
            payload={"urgent": True},
        )
        result = await governor.push_event(critical_event)
        assert result is True
        
        low_event = PrioritizedEvent(
            priority=EventPriority.P4_BACKGROUND,
            event_type="analytics",
            payload={},
        )
        result = await governor.push_event(low_event)
        assert result is False
        
        await governor.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
