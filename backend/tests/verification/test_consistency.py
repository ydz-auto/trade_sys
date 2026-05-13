"""
Cross-Mode Consistency Tests - 跨模式一致性测试

测试不同运行模式之间的一致性：
- Live vs Replay
- Live vs Backtest
- Replay vs Backtest
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from typing import Dict, List, Any

from infrastructure.runtime import (
    RuntimeEngine,
    RuntimeMode,
    RuntimeConfig,
    RuntimeState,
    create_live_runtime,
    create_paper_runtime,
    create_replay_runtime,
    create_backtest_runtime,
)
from infrastructure.verification import (
    ConsistencyTester,
    TestReport,
    TestType,
)


@pytest.fixture
def sample_events() -> List[Dict[str, Any]]:
    """示例事件"""
    base_time = datetime(2024, 1, 1, 0, 0, 0)
    return [
        {
            "event_type": "market",
            "symbol": "BTC/USDT",
            "exchange": "binance",
            "timestamp": (base_time + timedelta(minutes=i)).isoformat(),
            "price": 50000 + i * 10,
            "volume": 100,
        }
        for i in range(50)
    ]


class TestCrossModeRuntime:
    """跨模式运行时测试"""

    def test_create_live_runtime(self):
        """测试创建实时运行时"""
        runtime = create_live_runtime(
            strategy_id="test_strategy",
            initial_capital=100000.0,
        )
        assert runtime.config.mode == RuntimeMode.LIVE
        assert runtime.config.initial_capital == 100000.0

    def test_create_paper_runtime(self):
        """测试创建模拟运行时"""
        runtime = create_paper_runtime(
            strategy_id="test_strategy",
            initial_capital=50000.0,
        )
        assert runtime.config.mode == RuntimeMode.PAPER
        assert runtime.config.initial_capital == 50000.0

    def test_create_replay_runtime(self):
        """测试创建回放运行时"""
        start_time = datetime(2024, 1, 1)
        end_time = datetime(2024, 1, 2)
        
        runtime = create_replay_runtime(
            start_time=start_time,
            end_time=end_time,
            strategy_id="test_strategy",
            speed=1.0,
        )
        assert runtime.config.mode == RuntimeMode.REPLAY
        assert runtime.clock.config.mode.value == "replay"

    def test_create_backtest_runtime(self):
        """测试创建回测运行时"""
        start_time = datetime(2024, 1, 1)
        end_time = datetime(2024, 1, 2)
        
        runtime = create_backtest_runtime(
            start_time=start_time,
            end_time=end_time,
            strategy_id="test_strategy",
            initial_capital=100000.0,
        )
        assert runtime.config.mode == RuntimeMode.BACKTEST
        assert runtime.config.initial_capital == 100000.0


class TestRuntimeState:
    """运行时状态测试"""

    def test_runtime_state_creation(self):
        """测试运行时状态创建"""
        runtime = create_live_runtime()
        state = runtime.get_state()
        
        assert isinstance(state, RuntimeState)
        assert state.runtime_id == runtime.runtime_id
        assert state.capital == 100000.0

    def test_runtime_state_tracking(self):
        """测试运行时状态追踪"""
        runtime = create_replay_runtime(
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 1, 2),
        )
        
        assert runtime._state.events_processed == 0
        assert runtime._state.orders_created == 0
        assert runtime._state.orders_filled == 0


class TestEventHandlers:
    """事件处理器测试"""

    @pytest.mark.asyncio
    async def test_event_handler_registration(self, sample_events):
        """测试事件处理器注册"""
        runtime = create_replay_runtime(
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 1, 2),
        )
        
        handler_called = False
        
        async def test_handler(event):
            nonlocal handler_called
            handler_called = True
            return {"processed": True}
        
        runtime.register_event_handler("market", test_handler)
        
        await runtime.initialize()
        await runtime.start()
        
        await runtime.process_event(sample_events[0])
        
        assert handler_called
        await runtime.stop()

    @pytest.mark.asyncio
    async def test_multiple_handlers(self, sample_events):
        """测试多个处理器"""
        runtime = create_replay_runtime(
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 1, 2),
        )
        
        results = []
        
        async def handler1(event):
            results.append("handler1")
        
        async def handler2(event):
            results.append("handler2")
        
        runtime.register_event_handler("market", handler1)
        runtime.register_event_handler("market", handler2)
        
        await runtime.initialize()
        await runtime.start()
        
        await runtime.process_event(sample_events[0])
        
        assert len(results) == 2
        assert "handler1" in results
        assert "handler2" in results
        
        await runtime.stop()


class TestSnapshotIntegration:
    """快照集成测试"""

    @pytest.mark.asyncio
    async def test_snapshot_lifecycle(self, sample_events):
        """测试快照生命周期"""
        runtime = create_replay_runtime(
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 1, 2),
        )
        
        await runtime.initialize()
        await runtime.start()
        
        for event in sample_events[:10]:
            await runtime.process_event(event)
        
        state_before = runtime.get_state()
        assert state_before.events_processed == 10
        
        snapshot = await runtime.save_snapshot()
        assert snapshot is not None
        assert "runtime_id" in snapshot
        
        for event in sample_events[10:30]:
            await runtime.process_event(event)
        
        state_after = runtime.get_state()
        assert state_after.events_processed == 30
        
        await runtime.stop()


class TestConsistencyTester:
    """一致性测试器测试"""

    @pytest.mark.asyncio
    async def test_tester_initialization(self):
        """测试测试器初始化"""
        tester = ConsistencyTester()
        assert len(tester._test_cases) == 0
        assert len(tester._test_history) == 0

    @pytest.mark.asyncio
    async def test_cross_mode_test_execution(self, sample_events):
        """测试跨模式测试执行"""
        tester = ConsistencyTester()
        
        report = await tester.run_cross_mode_test(
            test_name="basic_cross_mode",
            events=sample_events[:10],
        )
        
        assert isinstance(report, TestReport)
        assert report.test_type == TestType.CROSS_MODE
        assert report.test_name == "basic_cross_mode"
        assert report.duration_ms > 0

    @pytest.mark.asyncio
    async def test_replay_determinism_test(self, sample_events):
        """测试回放确定性测试"""
        tester = ConsistencyTester()
        
        report = await tester.run_replay_determinism_test(
            test_name="basic_determinism",
            replay_runtime_factory=lambda: create_replay_runtime(
                start_time=datetime(2024, 1, 1),
                end_time=datetime(2024, 1, 2),
            ),
            event_source=sample_events[:10],
            runs=2,
        )
        
        assert isinstance(report, TestReport)
        assert report.test_type == TestType.REPLAY_DETERMINISM
        assert report.test_name == "basic_determinism"

    @pytest.mark.asyncio
    async def test_summary_generation(self):
        """测试摘要生成"""
        tester = ConsistencyTester()
        
        report = await tester.run_cross_mode_test(
            test_name="summary_test",
            events=[],
        )
        
        summary = tester.get_summary()
        
        assert summary["total"] >= 1
        assert "passed" in summary
        assert "failed" in summary


class TestRuntimeIntegration:
    """运行时集成测试"""

    @pytest.mark.asyncio
    async def test_full_runtime_lifecycle(self, sample_events):
        """测试完整运行时生命周期"""
        runtime = create_replay_runtime(
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 1, 2),
        )
        
        await runtime.initialize()
        assert runtime.clock is not None
        
        await runtime.start()
        assert runtime._running
        
        await runtime.pause()
        assert runtime._paused
        
        await runtime.resume()
        assert not runtime._paused
        
        for event in sample_events:
            await runtime.process_event(event)
        
        state = runtime.get_state()
        assert state.events_processed == len(sample_events)
        
        await runtime.stop()
        assert not runtime._running

    @pytest.mark.asyncio
    async def test_order_creation(self):
        """测试订单创建"""
        runtime = create_replay_runtime(
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 1, 2),
        )
        
        await runtime.initialize()
        await runtime.start()
        
        order_request = {
            "symbol": "BTC/USDT",
            "side": "buy",
            "quantity": 0.1,
            "price": 50000,
        }
        
        order = await runtime.create_order(order_request)
        
        await runtime.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
