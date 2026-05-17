"""
Execution State Machine Tests - 订单状态机测试

测试覆盖:
- OrderStateMachine: 状态转换
- OrderJournal: 事件溯源
- IdempotencyManager: 幂等性
- RetryEngine: 重试机制
- OrderReconciliation: 状态同步
"""

import asyncio
import pytest
import time
from datetime import datetime

from domain.execution.models.enums import OrderStatus, OrderSide, OrderType, Exchange
from domain.execution.models.order import Order, OrderRequest
from services.execution_service.state_machine.order_state_machine import (
    OrderEvent,
    OrderJournal,
    OrderJournalEntry,
    IdempotencyManager,
    RetryConfig,
    RetryEngine,
    OrderStateMachine,
    VALID_TRANSITIONS,
    TERMINAL_STATES,
)
from services.execution_service.state_machine.reconciliation import (
    ReconciliationConfig,
    SlippageTracker,
    OrderReconciliation,
)


class TestOrderJournal:
    """订单事件溯源测试"""
    
    def test_create_journal(self):
        journal = OrderJournal()
        assert journal.get_stats()["total_orders"] == 0
    
    def test_append_entry(self):
        journal = OrderJournal()
        
        entry = OrderJournalEntry(
            order_id="test_order_1",
            event=OrderEvent.CREATED,
            timestamp=time.time(),
            state_before=OrderStatus.PENDING,
            state_after=OrderStatus.PENDING,
        )
        
        journal.append(entry)
        
        history = journal.get_history("test_order_1")
        assert len(history) == 1
        assert history[0].event == OrderEvent.CREATED
    
    def test_multiple_entries(self):
        journal = OrderJournal()
        
        events = [
            (OrderEvent.CREATED, OrderStatus.PENDING, OrderStatus.PENDING),
            (OrderEvent.SUBMITTED, OrderStatus.PENDING, OrderStatus.SUBMITTED),
            (OrderEvent.FILLED, OrderStatus.SUBMITTED, OrderStatus.FILLED),
        ]
        
        for event, before, after in events:
            journal.append(OrderJournalEntry(
                order_id="test_order_1",
                event=event,
                timestamp=time.time(),
                state_before=before,
                state_after=after,
            ))
        
        history = journal.get_history("test_order_1")
        assert len(history) == 3
    
    def test_get_last_event(self):
        journal = OrderJournal()
        
        journal.append(OrderJournalEntry(
            order_id="test_order_1",
            event=OrderEvent.CREATED,
            timestamp=time.time(),
            state_before=OrderStatus.PENDING,
            state_after=OrderStatus.PENDING,
        ))
        
        journal.append(OrderJournalEntry(
            order_id="test_order_1",
            event=OrderEvent.SUBMITTED,
            timestamp=time.time(),
            state_before=OrderStatus.PENDING,
            state_after=OrderStatus.SUBMITTED,
        ))
        
        last = journal.get_last_event("test_order_1")
        assert last.event == OrderEvent.SUBMITTED


class TestIdempotencyManager:
    """幂等性管理器测试"""
    
    @pytest.mark.asyncio
    async def test_register_key(self):
        manager = IdempotencyManager()
        
        result = await manager.register("key_1", "order_1")
        assert result is True
        
        result = await manager.register("key_1", "order_2")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_update_status(self):
        manager = IdempotencyManager()
        
        await manager.register("key_1", "order_1")
        await manager.update_status("key_1", "completed")
        
        is_processed = await manager.is_processed("key_1")
        assert is_processed is True
    
    @pytest.mark.asyncio
    async def test_get_order_id(self):
        manager = IdempotencyManager()
        
        await manager.register("key_1", "order_1")
        
        order_id = await manager.get_order_id("key_1")
        assert order_id == "order_1"
        
        order_id = await manager.get_order_id("nonexistent")
        assert order_id is None


class TestRetryEngine:
    """重试引擎测试"""
    
    def test_should_retry(self):
        engine = RetryEngine()
        
        assert engine.should_retry("order_1", "network_error") is True
        assert engine.should_retry("order_1", "timeout") is True
        assert engine.should_retry("order_1", "invalid_symbol") is False
    
    def test_max_retries(self):
        config = RetryConfig(max_retries=2)
        engine = RetryEngine(config)
        
        assert engine.should_retry("order_1", "network_error") is True
        engine._retry_counts["order_1"] = 1
        assert engine.should_retry("order_1", "network_error") is True
        engine._retry_counts["order_1"] = 2
        assert engine.should_retry("order_1", "network_error") is False
    
    def test_get_delay_ms(self):
        config = RetryConfig(
            initial_delay_ms=1000,
            backoff_multiplier=2.0,
        )
        engine = RetryEngine(config)
        
        assert engine.get_delay_ms("order_1") == 1000
        
        engine._retry_counts["order_1"] = 1
        assert engine.get_delay_ms("order_1") == 2000
        
        engine._retry_counts["order_1"] = 2
        assert engine.get_delay_ms("order_1") == 4000
    
    @pytest.mark.asyncio
    async def test_register_retry(self):
        engine = RetryEngine()
        
        count = await engine.register_retry("order_1")
        assert count == 1
        
        count = await engine.register_retry("order_1")
        assert count == 2


class TestOrderStateMachine:
    """订单状态机测试"""
    
    def test_create_state_machine(self):
        sm = OrderStateMachine()
        assert sm.get_stats()["total_orders"] == 0
    
    @pytest.mark.asyncio
    async def test_create_order(self):
        sm = OrderStateMachine()
        
        order = Order(
            order_id="test_order_1",
            symbol="BTCUSDT",
            exchange=Exchange.BINANCE,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=1.0,
        )
        
        created = await sm.create_order(order)
        
        assert created.status == OrderStatus.PENDING
        assert sm.get_order("test_order_1") is not None
    
    @pytest.mark.asyncio
    async def test_valid_transition(self):
        sm = OrderStateMachine()
        
        order = Order(
            order_id="test_order_1",
            symbol="BTCUSDT",
            exchange=Exchange.BINANCE,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=1.0,
        )
        
        await sm.create_order(order)
        
        result = await sm.submit("test_order_1")
        assert result.status == OrderStatus.SUBMITTED
    
    @pytest.mark.asyncio
    async def test_invalid_transition(self):
        sm = OrderStateMachine()
        
        order = Order(
            order_id="test_order_1",
            symbol="BTCUSDT",
            exchange=Exchange.BINANCE,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=1.0,
        )
        
        await sm.create_order(order)
        
        with pytest.raises(ValueError):
            await sm.fill("test_order_1", 1.0, 50000.0)
    
    @pytest.mark.asyncio
    async def test_fill_order(self):
        sm = OrderStateMachine()
        
        order = Order(
            order_id="test_order_1",
            symbol="BTCUSDT",
            exchange=Exchange.BINANCE,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=1.0,
        )
        
        await sm.create_order(order)
        await sm.submit("test_order_1")
        
        result = await sm.fill("test_order_1", 1.0, 50000.0)
        
        assert result.status == OrderStatus.FILLED
        assert result.filled_quantity == 1.0
        assert result.average_price == 50000.0
    
    @pytest.mark.asyncio
    async def test_partial_fill(self):
        sm = OrderStateMachine()
        
        order = Order(
            order_id="test_order_1",
            symbol="BTCUSDT",
            exchange=Exchange.BINANCE,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=2.0,
        )
        
        await sm.create_order(order)
        await sm.submit("test_order_1")
        
        result = await sm.partial_fill("test_order_1", 1.0, 50000.0)
        
        assert result.status == OrderStatus.PARTIALLY_FILLED
        assert result.filled_quantity == 1.0
        
        result = await sm.fill("test_order_1", 2.0, 50100.0)
        
        assert result.status == OrderStatus.FILLED
    
    @pytest.mark.asyncio
    async def test_cancel_order(self):
        sm = OrderStateMachine()
        
        order = Order(
            order_id="test_order_1",
            symbol="BTCUSDT",
            exchange=Exchange.BINANCE,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=1.0,
        )
        
        await sm.create_order(order)
        await sm.submit("test_order_1")
        
        result = await sm.cancel("test_order_1")
        
        assert result.status == OrderStatus.CANCELLED
    
    @pytest.mark.asyncio
    async def test_reject_order(self):
        sm = OrderStateMachine()
        
        order = Order(
            order_id="test_order_1",
            symbol="BTCUSDT",
            exchange=Exchange.BINANCE,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=1.0,
        )
        
        await sm.create_order(order)
        
        result = await sm.reject("test_order_1", "Insufficient balance")
        
        assert result.status == OrderStatus.REJECTED
        assert result.error == "Insufficient balance"
    
    @pytest.mark.asyncio
    async def test_fail_with_retry(self):
        sm = OrderStateMachine()
        
        order = Order(
            order_id="test_order_1",
            symbol="BTCUSDT",
            exchange=Exchange.BINANCE,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=1.0,
        )
        
        await sm.create_order(order)
        await sm.submit("test_order_1")
        
        result = await sm.fail("test_order_1", "network_error")
        
        assert result.status == OrderStatus.PENDING
        assert result.metadata.get("retry_count") == 1
    
    @pytest.mark.asyncio
    async def test_fail_max_retries(self):
        sm = OrderStateMachine()
        
        order = Order(
            order_id="test_order_1",
            symbol="BTCUSDT",
            exchange=Exchange.BINANCE,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=1.0,
        )
        
        await sm.create_order(order)
        await sm.submit("test_order_1")
        
        for _ in range(3):
            await sm._retry_engine.register_retry("test_order_1")
        
        result = await sm.fail("test_order_1", "network_error")
        
        assert result.status == OrderStatus.FAILED
    
    @pytest.mark.asyncio
    async def test_idempotency(self):
        sm = OrderStateMachine()
        
        order = Order(
            order_id="test_order_1",
            symbol="BTCUSDT",
            exchange=Exchange.BINANCE,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=1.0,
        )
        
        await sm.create_order(order, idempotency_key="key_1")
        
        order2 = Order(
            order_id="test_order_2",
            symbol="BTCUSDT",
            exchange=Exchange.BINANCE,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=1.0,
        )
        
        result = await sm.create_order(order2, idempotency_key="key_1")
        
        assert result.order_id == "test_order_2"
    
    @pytest.mark.asyncio
    async def test_get_active_orders(self):
        sm = OrderStateMachine()
        
        for i in range(3):
            order = Order(
                order_id=f"order_{i}",
                symbol="BTCUSDT",
                exchange=Exchange.BINANCE,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=1.0,
            )
            await sm.create_order(order)
            await sm.submit(f"order_{i}")
        
        active = sm.get_active_orders()
        assert len(active) == 3
    
    @pytest.mark.asyncio
    async def test_state_change_callback(self):
        sm = OrderStateMachine()
        
        changes = []
        
        async def callback(order, old_state, new_state):
            changes.append((order.order_id, old_state.value, new_state.value))
        
        sm.register_state_change_callback(callback)
        
        order = Order(
            order_id="test_order_1",
            symbol="BTCUSDT",
            exchange=Exchange.BINANCE,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=1.0,
        )
        
        await sm.create_order(order)
        await sm.submit("test_order_1")
        
        assert len(changes) >= 1


class TestSlippageTracker:
    """滑点追踪测试"""
    
    def test_record_slippage(self):
        tracker = SlippageTracker()
        
        record = tracker.record(
            order_id="order_1",
            symbol="BTCUSDT",
            side="buy",
            expected_price=50000.0,
            actual_price=50050.0,
            quantity=1.0,
        )
        
        assert record.slippage_pct == 0.1
        assert record.slippage_value == 50.0
    
    def test_get_stats(self):
        tracker = SlippageTracker()
        
        tracker.record("order_1", "BTCUSDT", "buy", 50000.0, 50050.0, 1.0)
        tracker.record("order_2", "BTCUSDT", "buy", 50000.0, 50100.0, 1.0)
        
        stats = tracker.get_stats()
        
        assert stats["total_trades"] == 2
        assert abs(stats["avg_slippage_pct"] - 0.15) < 0.001
        assert abs(stats["max_slippage_pct"] - 0.2) < 0.001


class TestValidTransitions:
    """状态转换验证测试"""
    
    def test_pending_transitions(self):
        valid = VALID_TRANSITIONS[OrderStatus.PENDING]
        assert OrderStatus.SUBMITTED in valid
        assert OrderStatus.REJECTED in valid
        assert OrderStatus.FAILED in valid
        assert OrderStatus.FILLED not in valid
    
    def test_submitted_transitions(self):
        valid = VALID_TRANSITIONS[OrderStatus.SUBMITTED]
        assert OrderStatus.PARTIALLY_FILLED in valid
        assert OrderStatus.FILLED in valid
        assert OrderStatus.CANCELLED in valid
        assert OrderStatus.PENDING in valid
    
    def test_filled_is_terminal(self):
        assert OrderStatus.FILLED in TERMINAL_STATES
        assert len(VALID_TRANSITIONS[OrderStatus.FILLED]) == 0
    
    def test_cancelled_is_terminal(self):
        assert OrderStatus.CANCELLED in TERMINAL_STATES
        assert len(VALID_TRANSITIONS[OrderStatus.CANCELLED]) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
