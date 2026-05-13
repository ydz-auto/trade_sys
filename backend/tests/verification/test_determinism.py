"""
Determinism Verification Tests - 确定性验证测试

测试系统是否满足确定性要求：
- 同输入 = 同输出
- 同输入 = 同状态演化
"""

import asyncio
import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any

from infrastructure.runtime import (
    Clock,
    ClockMode,
    ClockConfig,
    RuntimeEngine,
    RuntimeMode,
    RuntimeConfig,
    RuntimeState,
    create_replay_runtime,
)
from infrastructure.verification import (
    DeterminismVerifier,
    VerificationResult,
    VerificationStatus,
    RunResult,
)


@pytest.fixture
def clock():
    """时钟 fixture"""
    config = ClockConfig(
        mode=ClockMode.REPLAY,
        start_time=datetime(2024, 1, 1, 0, 0, 0),
        end_time=datetime(2024, 1, 2, 0, 0, 0),
    )
    return Clock(config)


@pytest.fixture
def replay_runtime():
    """回放运行时 fixture"""
    config = RuntimeConfig(
        mode=RuntimeMode.REPLAY,
        start_time=datetime(2024, 1, 1, 0, 0, 0),
        end_time=datetime(2024, 1, 2, 0, 0, 0),
    )
    return RuntimeEngine(config)


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
        for i in range(100)
    ]


class TestClockDeterminism:
    """时钟确定性测试"""

    def test_clock_replay_mode_advances(self, clock):
        """测试回放模式下时钟推进"""
        initial_time = clock.now()
        
        clock.advance(timedelta(seconds=1))
        
        assert clock.now() > initial_time
        assert clock.is_simulated()

    def test_clock_time_consistency(self, clock):
        """测试时钟时间一致性"""
        times = []
        for _ in range(10):
            times.append(clock.now())
            clock.advance(timedelta(seconds=1))
        
        for i in range(1, len(times)):
            assert times[i] > times[i-1]
            expected_diff = timedelta(seconds=i)
            assert times[i] == times[0] + expected_diff

    def test_clock_freeze(self, clock):
        """测试时钟冻结"""
        clock.advance(timedelta(hours=1))
        frozen_time = clock.now()
        
        with clock.freeze():
            for _ in range(5):
                clock.advance(timedelta(hours=1))
        
        assert clock.now() == frozen_time


class TestRuntimeDeterminism:
    """运行时确定性测试"""

    def test_runtime_initial_state(self, replay_runtime):
        """测试运行时初始状态"""
        assert replay_runtime.runtime_id is not None
        assert replay_runtime.config.mode == RuntimeMode.REPLAY
        assert not replay_runtime._running

    @pytest.mark.asyncio
    async def test_runtime_lifecycle(self, replay_runtime):
        """测试运行时生命周期"""
        await replay_runtime.initialize()
        assert replay_runtime._state.is_running is False
        
        await replay_runtime.start()
        assert replay_runtime._running
        assert replay_runtime._state.is_running
        
        await replay_runtime.stop()
        assert not replay_runtime._running
        assert not replay_runtime._state.is_running

    @pytest.mark.asyncio
    async def test_runtime_state_tracking(self, replay_runtime):
        """测试运行时状态追踪"""
        await replay_runtime.initialize()
        await replay_runtime.start()
        
        initial_state = replay_runtime.get_state()
        
        for _ in range(10):
            await replay_runtime.process_event({
                "event_type": "market",
                "timestamp": datetime.utcnow().isoformat(),
            })
        
        final_state = replay_runtime.get_state()
        
        assert final_state.events_processed == 10
        
        await replay_runtime.stop()


class TestEventProcessingDeterminism:
    """事件处理确定性测试"""

    @pytest.mark.asyncio
    async def test_event_processing_count(self, replay_runtime, sample_events):
        """测试事件处理计数"""
        await replay_runtime.initialize()
        await replay_runtime.start()
        
        for event in sample_events[:50]:
            await replay_runtime.process_event(event)
        
        state = replay_runtime.get_state()
        assert state.events_processed == 50
        
        await replay_runtime.stop()

    @pytest.mark.asyncio
    async def test_event_order_preserved(self, replay_runtime, sample_events):
        """测试事件顺序保持"""
        await replay_runtime.initialize()
        await replay_runtime.start()
        
        processed_order = []
        
        async def track_handler(event):
            processed_order.append(event)
        
        replay_runtime.register_event_handler("market", track_handler)
        
        for event in sample_events[:10]:
            await replay_runtime.process_event(event)
        
        assert len(processed_order) == 10
        
        timestamps = [e["timestamp"] for e in processed_order]
        assert timestamps == sorted(timestamps)
        
        await replay_runtime.stop()


class TestDeterminismVerifier:
    """确定性验证器测试"""

    @pytest.mark.asyncio
    async def test_verifier_initialization(self):
        """测试验证器初始化"""
        verifier = DeterminismVerifier()
        assert len(verifier._verification_history) == 0

    @pytest.mark.asyncio
    async def test_determinism_verification_pass(self, sample_events):
        """测试确定性验证通过"""
        verifier = DeterminismVerifier()
        run_count = 0
        
        async def deterministic_run() -> RunResult:
            nonlocal run_count
            run_count += 1
            
            config = RuntimeConfig(
                mode=RuntimeMode.REPLAY,
                start_time=datetime(2024, 1, 1, 0, 0, 0),
            )
            runtime = RuntimeEngine(config)
            
            await runtime.initialize()
            await runtime.start()
            
            for event in sample_events[:10]:
                await runtime.process_event(event)
            
            state = runtime.get_state()
            
            await runtime.stop()
            
            return RunResult(
                run_id=f"run_{run_count}",
                run_number=run_count,
                events=sample_events[:10],
                final_state=state.to_dict(),
                state_hash=str(state.events_processed),
                execution_time_ms=100,
                events_hash="test_hash",
                order_count=0,
                fill_count=0,
            )
        
        result = await verifier.verify_determinism(
            test_name="test_verification",
            run_function=deterministic_run,
            runs=3,
        )
        
        assert result.is_passed()
        assert len(result.differences) == 0

    def test_state_comparison(self):
        """测试状态比较"""
        verifier = DeterminismVerifier()
        
        state_a = {"a": 1, "b": 2, "c": 3}
        state_b = {"a": 1, "b": 2, "c": 3}
        state_c = {"a": 1, "b": 2, "c": 4}
        
        diff_a_b = verifier._compare_states(state_a, state_b)
        diff_a_c = verifier._compare_states(state_a, state_c)
        
        assert len(diff_a_b) == 0
        assert len(diff_a_c) == 1
        assert diff_a_c[0]["type"] == "value_mismatch"

    def test_nested_state_comparison(self):
        """测试嵌套状态比较"""
        verifier = DeterminismVerifier()
        
        state_a = {
            "portfolio": {"capital": 100000, "positions": {"BTC": 1.0}},
            "execution": {"orders": 10, "fills": 8},
        }
        state_b = {
            "portfolio": {"capital": 100000, "positions": {"BTC": 1.0}},
            "execution": {"orders": 10, "fills": 8},
        }
        state_c = {
            "portfolio": {"capital": 100001, "positions": {"BTC": 1.0}},
            "execution": {"orders": 10, "fills": 8},
        }
        
        diff_a_b = verifier._compare_states(state_a, state_b)
        diff_a_c = verifier._compare_states(state_a, state_c)
        
        assert len(diff_a_b) == 0
        assert len(diff_a_c) == 1


class TestVerificationHistory:
    """验证历史测试"""

    @pytest.mark.asyncio
    async def test_history_tracking(self):
        """测试历史追踪"""
        verifier = DeterminismVerifier()
        
        async def dummy_run():
            return RunResult(
                run_id="test",
                run_number=1,
                events=[],
                final_state={},
                state_hash="hash1",
                execution_time_ms=100,
                events_hash="events_hash",
                order_count=0,
                fill_count=0,
            )
        
        await verifier.verify_determinism("test1", dummy_run, runs=1)
        await verifier.verify_determinism("test2", dummy_run, runs=1)
        
        history = verifier.get_history()
        assert len(history) == 2

    @pytest.mark.asyncio
    async def test_summary_generation(self):
        """测试摘要生成"""
        verifier = DeterminismVerifier()
        
        async def dummy_run():
            return RunResult(
                run_id="test",
                run_number=1,
                events=[],
                final_state={},
                state_hash="hash",
                execution_time_ms=100,
                events_hash="events_hash",
                order_count=0,
                fill_count=0,
            )
        
        await verifier.verify_determinism("test1", dummy_run, runs=1)
        await verifier.verify_determinism("test2", dummy_run, runs=1)
        
        summary = verifier.get_summary()
        
        assert summary["total"] == 2
        assert "passed" in summary
        assert "failed" in summary
        assert "pass_rate" in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
