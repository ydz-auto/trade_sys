"""
Execution Runtime - 订单执行运行时

职责：
- 订单状态唯一 owner (pending_orders / fills / reconciliation)
- Kafka 消费 / 生命周期管理
- 风控检查委托
- 执行引擎委托

不变量：
- 所有 order 状态变更必须通过此 runtime
- OrderStateMachine 是唯一状态管理器
- 外部只能通过 RuntimeBus 发送 command 来修改 order
"""
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from runtime.kernel.base import BaseRuntime, RuntimeConfig
from runtime.kernel.shared import (
    RuntimeLifecycle,
    RuntimeMetrics,
    RuntimeHealthCheck,
)
from infrastructure.messaging.runtime_consumer import RuntimeConsumer, ConsumerConfig
from infrastructure.messaging.runtime_publisher import RuntimePublisher, PublisherConfig
from infrastructure.messaging.topics import Topics
from infrastructure.messaging.kafka_config import ConsumerGroup
from infrastructure.utilities.runtime_clock import get_clock, now_ms
from domain.feature.availability import get_systematic_guard
from domain.feature.label_isolation import get_label_store
from infrastructure.storage.immutable_snapshot import get_immutable_snapshot_store


class ExecutionConfig(RuntimeConfig):
    name: str = "execution_runtime"
    max_position_size: float = 0.1
    max_leverage: int = 5
    enable_mock: bool = True


class ExecutionRuntime(BaseRuntime):
    """
    Execution Runtime - 订单执行运行时

    单一状态 owner：
    - pending_orders -> self._state_machine
    - order_state -> self._state_machine
    - fill_lifecycle -> self._state_machine
    - execution_reconciliation -> self._state_machine
    """

    def __init__(self, config: ExecutionConfig = None):
        config = config or ExecutionConfig.from_env()
        super().__init__(config)
        self.config: ExecutionConfig = config

        self._clock = get_clock()
        self._availability_guard = get_systematic_guard()
        self._label_store = get_label_store()
        self._snapshot_store = None

        self.lifecycle: Optional[RuntimeLifecycle] = None
        self.metrics: Optional[RuntimeMetrics] = None
        self.health_check: Optional[RuntimeHealthCheck] = None

        self.consumer: Optional[RuntimeConsumer] = None
        self.publisher: Optional[RuntimePublisher] = None

        self._state_machine = None
        self._execution_engine = None
        self._risk_engine = None

    async def initialize(self) -> None:
        self.logger.info("Initializing Execution Runtime with time-causal infrastructure...")

        self._snapshot_store = get_immutable_snapshot_store("execution")

        self.lifecycle = RuntimeLifecycle("execution")
        self.metrics = RuntimeMetrics("execution")
        self.health_check = RuntimeHealthCheck("execution")

        try:
            self.consumer = RuntimeConsumer(ConsumerConfig(
                bootstrap_servers=self.config.kafka_bootstrap_servers,
                topics=[Topics.DECISIONS],
                group_id=ConsumerGroup.EXECUTION_RUNTIME,
            ))

            self.publisher = RuntimePublisher(PublisherConfig(
                bootstrap_servers=self.config.kafka_bootstrap_servers,
                topic=Topics.ORDERS,
            ))

            await self.consumer.start()
            await self.publisher.start()
        except Exception as e:
            self.logger.warning(f"Kafka transport unavailable, execution runtime running degraded: {e}")
            self.consumer = None
            self.publisher = None

        try:
            from runtimes.execution_runtime.state_machine.order_state_machine import (
                OrderStateMachine,
                OrderJournal,
                IdempotencyManager,
                RetryEngine,
            )
            self._state_machine = OrderStateMachine(
                journal=OrderJournal(),
                idempotency=IdempotencyManager(),
                retry_engine=RetryEngine(),
            )
            self.logger.info("OrderStateMachine initialized (single state owner)")
        except Exception as e:
            self.logger.warning(f"OrderStateMachine init failed: {e}")

        try:
            from runtimes.execution_runtime.engine.execution_engine import ExecutionEngine
            self._execution_engine = ExecutionEngine()
            self.logger.info("Execution engine initialized (compute delegate)")
        except Exception as e:
            self.logger.warning(f"Execution engine init failed: {e}")

        try:
            from engines.compute.risk.engine import RiskEngine
            self._risk_engine = RiskEngine()
            self.logger.info("Risk engine initialized (compute delegate)")
        except Exception as e:
            self.logger.warning(f"Risk engine init failed: {e}")

        self.health_check.register_check("state_machine", self._check_state_machine)
        self.health_check.register_check("execution_engine", self._check_execution_engine)
        self.health_check.register_check("risk_engine", self._check_risk_engine)
        self.health_check.register_check("consumer", self._check_consumer)
        self.health_check.register_check("publisher", self._check_publisher)

        self.logger.info("Execution Runtime initialized successfully")

    async def _check_state_machine(self) -> bool:
        return self._state_machine is not None

    async def _check_execution_engine(self) -> bool:
        return self._execution_engine is not None

    async def _check_risk_engine(self) -> bool:
        return self._risk_engine is not None

    async def _check_consumer(self) -> bool:
        return self.consumer is not None and await self.consumer.is_healthy()

    async def _check_publisher(self) -> bool:
        return self.publisher is not None and await self.publisher.is_healthy()

    def get_state(self) -> Dict[str, Any]:
        if self._state_machine:
            stats = self._state_machine.get_stats()
            orders = {}
            for order_id in list(self._state_machine._orders.keys())[:100]:
                order = self._state_machine.get_order(order_id)
                if order and hasattr(order, 'to_dict'):
                    orders[order_id] = order.to_dict()
                elif order:
                    orders[order_id] = {
                        "order_id": order.order_id,
                        "symbol": order.symbol,
                        "status": order.status.value if hasattr(order.status, 'value') else str(order.status),
                        "side": order.side.value if hasattr(order.side, 'value') else str(order.side),
                        "quantity": order.quantity,
                    }
            return {
                "orders": orders,
                "state": self.state.value if hasattr(self, 'state') else "unknown",
                "last_error": None,
                "stats": stats,
            }
        return {"orders": {}, "state": self.state.value if hasattr(self, 'state') else "unknown", "last_error": None}

    async def snapshot(self) -> Dict[str, Any]:
        ts = now_ms()
        return {
            "name": self.config.name,
            "state": self.state.value,
            "timestamp": ts,
            "business_state": self.get_state(),
        }

    async def recover(self, checkpoint: Any = None) -> None:
        await super().recover(checkpoint)
        if not isinstance(checkpoint, dict):
            return
        business_state = checkpoint.get("business_state")
        if business_state and self._state_machine:
            orders_data = business_state.get("orders", {})
            for order_id, order_data in orders_data.items():
                if order_id not in self._state_machine._orders:
                    self._state_machine._orders[order_id] = order_data

    async def create_order(self, order_data: Dict[str, Any]) -> Optional[Any]:
        if not self._state_machine:
            self.logger.warning("State machine not available")
            return None

        from domain.execution.models.order import Order
        from domain.execution.models.enums import OrderStatus, OrderSide, OrderType, Exchange

        order = Order(
            order_id=order_data.get("order_id", f"ord_{now_ms()}"),
            symbol=order_data.get("symbol", "BTCUSDT"),
            exchange=Exchange(order_data.get("exchange", "binance")),
            side=OrderSide(order_data.get("side", "buy")),
            order_type=OrderType(order_data.get("order_type", "market")),
            quantity=order_data.get("quantity", 0.01),
            price=order_data.get("price"),
            status=OrderStatus.PENDING,
        )

        idempotency_key = order_data.get("idempotency_key")
        result = await self._state_machine.create_order(order, idempotency_key=idempotency_key)
        self.metrics.increment("orders_created")
        return result

    async def transition_order(self, order_id: str, new_status: str, event: str, data: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        if not self._state_machine:
            return None

        from domain.execution.models.enums import OrderStatus
        from runtimes.execution_runtime.state_machine.order_state_machine import OrderEvent

        try:
            status = OrderStatus(new_status)
            evt = OrderEvent(event)
            return await self._state_machine.transition(order_id, status, evt, data)
        except (ValueError, KeyError) as e:
            self.logger.error(f"Invalid transition: {order_id} -> {new_status} ({event}): {e}")
            return None

    async def cancel_order(self, order_id: str) -> bool:
        if not self._state_machine:
            return False
        try:
            await self._state_machine.cancel(order_id)
            self.metrics.increment("orders_cancelled")
            return True
        except ValueError:
            return False

    async def get_order(self, order_id: str) -> Optional[Any]:
        if not self._state_machine:
            return None
        return self._state_machine.get_order(order_id)

    async def get_pending_orders(self) -> List[Any]:
        if not self._state_machine:
            return []
        return self._state_machine.get_pending_orders()

    async def get_active_orders(self) -> List[Any]:
        if not self._state_machine:
            return []
        return self._state_machine.get_active_orders()

    async def shutdown(self) -> None:
        self.logger.info("Shutting down Execution Runtime...")

        if self.consumer:
            await self.consumer.stop()
        if self.publisher:
            await self.publisher.stop()

        self.logger.info(f"Execution Runtime stopped. Stats: {self.metrics.to_dict()}")

    async def run(self) -> None:
        self.logger.info("Starting Execution Runtime main loop...")

        await self.lifecycle.transition_to_running()

        while not self.context.is_shutdown_requested():
            try:
                if self.consumer is None:
                    await asyncio.sleep(1.0)
                    continue
                message = await self.consumer.consume(timeout=1.0)
                if message:
                    await self._process_decision(message)
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                self.metrics.increment("errors")
                await self.lifecycle.handle_error(e)

    async def _process_decision(self, decision: Dict[str, Any]) -> None:
        from infrastructure.messaging.schema.base_event import OrderEvent, EventSource
        from infrastructure.messaging.event_registry import parse_event
        from runtime.contracts import to_immutable_event, to_transport_event
        trace_id = decision.get("trace_id", "unknown")

        if self._label_store:
            self._label_store.ensure_isolation("execution")

        self.metrics.increment("decisions_received")

        with self.metrics.timing("decision_processing"):
            try:
                base_event = parse_event(decision)
                canonical_event = to_immutable_event(base_event)
            except Exception:
                canonical_event = None

            risk_result = await self._check_risk(decision)

            if not risk_result.get("approved", False):
                self.logger.warning(f"[{trace_id}] Risk check failed: {risk_result.get('reason')}")
                self.metrics.increment("risk_rejected")
                return

            order = await self._execute_decision(decision)

            if order:
                if self._snapshot_store:
                    self._snapshot_store.save(order, timestamp=now_ms())

                self.metrics.increment("orders_executed")
                self.logger.info(f"[{trace_id}] Order executed: {order}")

                if isinstance(order, dict):
                    order_event = OrderEvent(
                        source=EventSource.EXECUTION_RUNTIME,
                        symbol=order.get("symbol", "BTCUSDT"),
                        event_time_ms=now_ms(),
                        order_id=order.get("order_id", f"ord_{now_ms()}"),
                        side=order.get("side", "buy"),
                        order_type=order.get("type", "market"),
                        quantity=order.get("quantity", 0),
                        price=order.get("price"),
                        status=order.get("status", "new"),
                        trace_id=order.get("trace_id", trace_id),
                    )
                    if self.publisher:
                        await self.publisher.publish(order_event)
                else:
                    order_event = OrderEvent(
                        source=EventSource.EXECUTION_RUNTIME,
                        symbol=getattr(order, "symbol", "BTCUSDT"),
                        event_time_ms=now_ms(),
                        order_id=getattr(order, "order_id", f"ord_{now_ms()}"),
                        side=getattr(order, "side", "buy"),
                        order_type=getattr(order, "order_type", "market"),
                        quantity=getattr(order, "quantity", 0),
                        price=getattr(order, "price"),
                        status=getattr(order, "status", "new"),
                        trace_id=trace_id,
                    )
                    if self.publisher:
                        await self.publisher.publish(order_event)

    async def _check_risk(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        if self._risk_engine:
            return await self._risk_engine.check(decision)
        return {"approved": True, "reason": "Risk engine not available"}

    async def _execute_decision(self, decision: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if decision.get("action") == "HOLD":
            return None

        if self._execution_engine:
            return await self._execution_engine.execute(decision)

        return self._create_mock_order(decision)

    def _create_mock_order(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        from infrastructure.messaging.schema.base_event import OrderEvent, EventSource
        event = OrderEvent(
            source=EventSource.EXECUTION_RUNTIME,
            symbol=decision.get("symbol", "BTCUSDT"),
            event_time_ms=now_ms(),
            order_id=f"ord_{now_ms()}",
            side="buy" if decision.get("action") == "LONG" else "sell",
            order_type="market",
            quantity=decision.get("quantity", 0.01),
            status="filled",
            trace_id=decision.get("trace_id", ""),
        )
        return event.to_dict()

    async def execute_signal(self, signal: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not signal:
            return None

        signal_type = signal.get('signal_type')
        if signal_type not in ['buy', 'sell', 'long', 'short']:
            return None

        decision = {
            "action": "LONG" if signal_type in ['buy', 'long'] else "SHORT",
            "symbol": signal.get('symbol', 'BTCUSDT'),
            "quantity": signal.get('quantity', 0.01),
            "confidence": signal.get('confidence', 1.0),
            "reason": signal.get('reason', ''),
            "trace_id": f"signal_{signal.get('timestamp_ms', now_ms())}",
        }

        risk_result = await self._check_risk(decision)
        if not risk_result.get("approved", False):
            self.logger.debug(f"Signal rejected by risk check: {risk_result.get('reason')}")
            return None

        order = await self._execute_decision(decision)

        if order:
            return {
                "order_id": order.get("order_id"),
                "symbol": order.get("symbol"),
                "side": order.get("side"),
                "quantity": order.get("quantity"),
                "pnl": 0.0,
                "pnl_pct": 0.0,
                "timestamp": order.get("timestamp"),
            }

        return None

    async def health_check(self) -> Dict[str, Any]:
        health = await super().health_check()
        health.update({
            "lifecycle": self.lifecycle.to_dict() if self.lifecycle else {},
            "metrics": self.metrics.to_dict() if self.metrics else {},
            "health_check": await self.health_check.to_dict() if self.health_check else {},
        })
        return health


_execution_runtime: Optional[ExecutionRuntime] = None


def get_execution_runtime() -> ExecutionRuntime:
    global _execution_runtime
    if _execution_runtime is None:
        _execution_runtime = ExecutionRuntime()
    return _execution_runtime


async def main():
    print("=" * 60)
    print("Execution Runtime - Risk Check + Order Execution")
    print("=" * 60)

    runtime = get_execution_runtime()
    await runtime.start()


if __name__ == "__main__":
    asyncio.run(main())
