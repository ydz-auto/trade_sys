import asyncio
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid

from domain.execution.models.enums import OrderStatus, OrderSide, OrderType, Exchange, MarketType
from domain.execution.models.order import Order, OrderRequest, OrderIntent
from infrastructure.logging import get_logger
from infrastructure.utilities.runtime_clock import now_ms
from infrastructure.messaging.schema.base_event import OrderEvent as PipelineOrderEvent, EventSource
from domain.execution.state_machine.order_state_machine import (
    OrderStateMachine,
    OrderJournal,
    IdempotencyManager,
    RetryEngine,
    OrderEvent,
)
from domain.execution.state_machine.reconciliation import (
    OrderReconciliation,
    ReconciliationConfig,
    SlippageTracker,
)

logger = get_logger("execution.engine_with_state_machine")

_ORDER_EVENT_PRIORITIES = {
    OrderStatus.FILLED: "critical",
    OrderStatus.REJECTED: "critical",
    OrderStatus.FAILED: "critical",
    OrderStatus.PARTIALLY_FILLED: "high",
    OrderStatus.CANCELLED: "high",
}

_DEFAULT_PRIORITY = "normal"


class ExecutionEngineWithStateMachine:
    def __init__(
        self,
        exchange_adapters: Optional[Dict[str, Any]] = None,
        enable_reconciliation: bool = True,
        event_bus=None,
    ):
        self._journal = OrderJournal()
        self._idempotency = IdempotencyManager()
        self._retry_engine = RetryEngine()
        self._state_machine = OrderStateMachine(
            journal=self._journal,
            idempotency=self._idempotency,
            retry_engine=self._retry_engine,
        )

        self._reconciliation_config = ReconciliationConfig()
        self._reconciliation = OrderReconciliation(
            self._state_machine,
            self._reconciliation_config,
        )

        self._exchange_adapters = exchange_adapters or {}
        self._event_bus = event_bus
        if self._event_bus is None:
            from domain.event.kernel_event import get_runtime_bus
            self._event_bus = get_runtime_bus()

        self._running = False
        self._stats = {
            "total_orders": 0,
            "successful_orders": 0,
            "failed_orders": 0,
            "total_volume": 0.0,
        }

        self._state_machine.register_state_change_callback(
            self._on_state_change
        )

    def register_exchange_adapter(self, exchange: str, adapter: Any) -> None:
        self._exchange_adapters[exchange] = adapter
        self._reconciliation.register_exchange_adapter(exchange, adapter)
        logger.info(f"Registered exchange adapter: {exchange}")

    async def _on_state_change(
        self,
        order: Order,
        old_state: OrderStatus,
        new_state: OrderStatus,
    ) -> None:
        priority = _ORDER_EVENT_PRIORITIES.get(new_state, _DEFAULT_PRIORITY)
        order_event = PipelineOrderEvent(
            source=EventSource.EXECUTION_SERVICE,
            symbol=order.symbol,
            event_time_ms=now_ms(),
            order_id=order.order_id,
            side=order.side.value,
            order_type=order.order_type.value,
            quantity=order.quantity,
            price=order.price,
            filled_quantity=order.filled_quantity,
            status=new_state.value,
            metadata={"old_state": old_state.value, "priority": priority},
        )
        await self._event_bus.publish_event(order_event)

    async def start(self) -> None:
        if self._running:
            return

        self._running = True

        if self._reconciliation_config:
            await self._reconciliation.start()

        logger.info("Execution Engine with State Machine started")

    async def stop(self) -> None:
        if not self._running:
            return

        self._running = False

        await self._reconciliation.stop()

        logger.info("Execution Engine with State Machine stopped")

    async def submit_order(
        self,
        request: OrderRequest,
        idempotency_key: Optional[str] = None,
    ) -> Order:
        order_id = str(uuid.uuid4())

        order = Order(
            order_id=order_id,
            symbol=request.symbol,
            exchange=request.exchange,
            side=request.side,
            order_type=request.order_type,
            quantity=request.quantity,
            price=request.price,
            market_type=request.market_type,
            client_order_id=request.client_order_id,
        )

        order = await self._state_machine.create_order(order, idempotency_key)

        self._stats["total_orders"] += 1

        try:
            adapter = self._exchange_adapters.get(request.exchange.value)

            if not adapter:
                raise ValueError(f"No adapter for exchange: {request.exchange.value}")

            exchange_result = await adapter.submit_order(
                symbol=request.symbol,
                side=request.side.value,
                order_type=request.order_type.value,
                quantity=request.quantity,
                price=request.price,
                client_order_id=order_id,
            )

            order.exchange_order_id = exchange_result.get("orderId")

            await self._state_machine.submit(order.order_id)

            logger.info(
                f"Order submitted: {order.order_id} -> {order.exchange_order_id} "
                f"({request.symbol} {request.side.value} {request.quantity})"
            )

            return order

        except Exception as e:
            error_str = str(e)
            logger.error(f"Order submission failed: {order_id} - {error_str}")

            try:
                await self._state_machine.fail(order.order_id, error_str)
            except Exception:
                pass

            self._stats["failed_orders"] += 1

            raise

    async def submit_intent(
        self,
        intent: OrderIntent,
        order_type: OrderType = OrderType.MARKET,
        price: Optional[float] = None,
    ) -> Order:
        request = intent.to_order_request(order_type, price)
        return await self.submit_order(request)

    async def cancel_order(self, order_id: str) -> Order:
        order = self._state_machine.get_order(order_id)

        if not order:
            raise ValueError(f"Order not found: {order_id}")

        if not order.exchange_order_id:
            return await self._state_machine.cancel(order_id)

        try:
            adapter = self._exchange_adapters.get(order.exchange.value)

            if not adapter:
                raise ValueError(f"No adapter for exchange: {order.exchange.value}")

            await adapter.cancel_order(order.exchange_order_id)

            return await self._state_machine.cancel(order_id)

        except Exception as e:
            logger.error(f"Order cancellation failed: {order_id} - {e}")
            raise

    async def get_order(self, order_id: str) -> Optional[Order]:
        return self._state_machine.get_order(order_id)

    async def get_active_orders(self) -> List[Order]:
        return self._state_machine.get_active_orders()

    async def get_order_history(self, order_id: str) -> List[Any]:
        return self._state_machine.get_history(order_id)

    def on_fill(
        self,
        exchange_order_id: str,
        filled_quantity: float,
        average_price: float,
        is_complete: bool,
    ) -> None:
        asyncio.create_task(
            self._handle_fill(exchange_order_id, filled_quantity, average_price, is_complete)
        )

    async def _handle_fill(
        self,
        exchange_order_id: str,
        filled_quantity: float,
        average_price: float,
        is_complete: bool,
    ) -> None:
        order = None
        for o in self._state_machine._orders.values():
            if o.exchange_order_id == exchange_order_id:
                order = o
                break

        if not order:
            logger.warning(f"Fill event for unknown order: {exchange_order_id}")
            return

        try:
            if is_complete:
                await self._state_machine.fill(
                    order.order_id,
                    filled_quantity,
                    average_price,
                )
                self._stats["successful_orders"] += 1
                self._stats["total_volume"] += filled_quantity * average_price
            else:
                await self._state_machine.partial_fill(
                    order.order_id,
                    filled_quantity,
                    average_price,
                )

            logger.info(
                f"Order fill: {order.order_id} filled={filled_quantity} "
                f"avg_price={average_price} complete={is_complete}"
            )

        except Exception as e:
            logger.error(f"Failed to process fill event: {e}")

    def on_order_rejected(self, exchange_order_id: str, reason: str) -> None:
        asyncio.create_task(
            self._handle_rejection(exchange_order_id, reason)
        )

    async def _handle_rejection(
        self,
        exchange_order_id: str,
        reason: str,
    ) -> None:
        order = None
        for o in self._state_machine._orders.values():
            if o.exchange_order_id == exchange_order_id:
                order = o
                break

        if not order:
            logger.warning(f"Rejection for unknown order: {exchange_order_id}")
            return

        try:
            await self._state_machine.reject(order.order_id, reason)
            self._stats["failed_orders"] += 1

            logger.info(f"Order rejected: {order.order_id} - {reason}")

        except Exception as e:
            logger.error(f"Failed to process rejection: {e}")

    async def reconcile(self) -> List[Any]:
        return await self._reconciliation.reconcile_all()

    def get_stats(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "engine_stats": self._stats,
            "state_machine_stats": self._state_machine.get_stats(),
            "reconciliation_stats": self._reconciliation.get_stats(),
        }

    def get_slippage_stats(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        return self._reconciliation.get_slippage_stats(symbol)


_execution_engine: Optional[ExecutionEngineWithStateMachine] = None


def get_execution_engine() -> ExecutionEngineWithStateMachine:
    global _execution_engine
    if _execution_engine is None:
        _execution_engine = ExecutionEngineWithStateMachine()
    return _execution_engine
