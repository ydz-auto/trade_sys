import asyncio
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Callable, Awaitable
from datetime import datetime
import time
import uuid
import json

from domain.execution.models.enums import OrderStatus, OrderSide, OrderType, Exchange
from domain.execution.models.order import Order, OrderRequest, OrderIntent
from infrastructure.logging import get_logger

logger = get_logger("execution.state_machine")


class OrderEvent(str, Enum):
    CREATED = "created"
    SUBMITTING = "submitting"
    SUBMITTED = "submitted"
    PARTIAL_FILL = "partial_fill"
    FILLED = "filled"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    FAILED = "failed"
    EXPIRED = "expired"
    RETRY = "retry"
    RECONCILED = "reconciled"


@dataclass
class OrderStateTransition:
    from_state: OrderStatus
    to_state: OrderStatus
    event: OrderEvent
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


VALID_TRANSITIONS: Dict[OrderStatus, List[OrderStatus]] = {
    OrderStatus.PENDING: [
        OrderStatus.SUBMITTED,
        OrderStatus.REJECTED,
        OrderStatus.FAILED,
        OrderStatus.CANCELLED,
    ],
    OrderStatus.SUBMITTED: [
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.FILLED,
        OrderStatus.CANCELLED,
        OrderStatus.REJECTED,
        OrderStatus.FAILED,
        OrderStatus.EXPIRED,
        OrderStatus.PENDING,
    ],
    OrderStatus.PARTIALLY_FILLED: [
        OrderStatus.FILLED,
        OrderStatus.CANCELLED,
        OrderStatus.REJECTED,
        OrderStatus.FAILED,
    ],
    OrderStatus.FILLED: [],
    OrderStatus.CANCELLED: [],
    OrderStatus.REJECTED: [OrderStatus.PENDING],
    OrderStatus.FAILED: [OrderStatus.PENDING],
    OrderStatus.EXPIRED: [],
}

TERMINAL_STATES = {
    OrderStatus.FILLED,
    OrderStatus.CANCELLED,
    OrderStatus.REJECTED,
    OrderStatus.EXPIRED,
}


@dataclass
class OrderJournalEntry:
    order_id: str
    event: OrderEvent
    timestamp: float
    state_before: OrderStatus
    state_after: OrderStatus
    data: Dict[str, Any] = field(default_factory=dict)
    idempotency_key: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "event": self.event.value,
            "timestamp": self.timestamp,
            "state_before": self.state_before.value,
            "state_after": self.state_after.value,
            "data": self.data,
            "idempotency_key": self.idempotency_key,
        }


class OrderJournal:
    def __init__(self, max_entries: int = 10000):
        self._entries: Dict[str, List[OrderJournalEntry]] = {}
        self._max_entries = max_entries
        self._all_entries: List[OrderJournalEntry] = []

    def append(self, entry: OrderJournalEntry) -> None:
        if entry.order_id not in self._entries:
            self._entries[entry.order_id] = []

        self._entries[entry.order_id].append(entry)
        self._all_entries.append(entry)

        if len(self._all_entries) > self._max_entries:
            oldest = self._all_entries.pop(0)
            if oldest.order_id in self._entries:
                self._entries[oldest.order_id] = [
                    e for e in self._entries[oldest.order_id]
                    if e.timestamp > oldest.timestamp
                ]

        logger.debug(
            f"Journal: {entry.order_id} {entry.state_before.value} -> "
            f"{entry.state_after.value} ({entry.event.value})"
        )

    def get_history(self, order_id: str) -> List[OrderJournalEntry]:
        return self._entries.get(order_id, [])

    def get_last_event(self, order_id: str) -> Optional[OrderJournalEntry]:
        history = self._entries.get(order_id, [])
        return history[-1] if history else None

    def get_all_entries(self, limit: int = 100) -> List[OrderJournalEntry]:
        return self._all_entries[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_orders": len(self._entries),
            "total_events": len(self._all_entries),
            "max_entries": self._max_entries,
        }


class IdempotencyManager:
    def __init__(self, ttl_seconds: float = 3600):
        self._keys: Dict[str, Dict[str, Any]] = {}
        self._ttl = ttl_seconds
        self._lock = asyncio.Lock()

    def generate_key(self, order: Order) -> str:
        return f"{order.symbol}_{order.side.value}_{order.quantity}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"

    async def register(self, key: str, order_id: str) -> bool:
        async with self._lock:
            now = time.time()

            expired_keys = [
                k for k, v in self._keys.items()
                if now - v["created_at"] > self._ttl
            ]
            for k in expired_keys:
                del self._keys[k]

            if key in self._keys:
                logger.warning(f"Idempotency key already exists: {key}")
                return False

            self._keys[key] = {
                "order_id": order_id,
                "created_at": now,
                "status": "pending",
            }
            return True

    async def update_status(self, key: str, status: str) -> None:
        async with self._lock:
            if key in self._keys:
                self._keys[key]["status"] = status

    async def get_order_id(self, key: str) -> Optional[str]:
        async with self._lock:
            entry = self._keys.get(key)
            return entry["order_id"] if entry else None

    async def is_processed(self, key: str) -> bool:
        async with self._lock:
            entry = self._keys.get(key)
            if not entry:
                return False
            return entry["status"] in ("completed", "failed")

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_keys": len(self._keys),
            "ttl_seconds": self._ttl,
        }


@dataclass
class RetryConfig:
    max_retries: int = 3
    initial_delay_ms: int = 1000
    max_delay_ms: int = 30000
    backoff_multiplier: float = 2.0
    retryable_errors: tuple = (
        "network_error",
        "timeout",
        "rate_limit",
        "service_unavailable",
    )


class RetryEngine:
    def __init__(self, config: RetryConfig = RetryConfig()):
        self._config = config
        self._retry_counts: Dict[str, int] = {}
        self._pending_retries: Dict[str, float] = {}
        self._lock = asyncio.Lock()

    def should_retry(self, order_id: str, error: str) -> bool:
        current_count = self._retry_counts.get(order_id, 0)

        if current_count >= self._config.max_retries:
            return False

        is_retryable = any(
            retryable in error.lower()
            for retryable in self._config.retryable_errors
        )

        return is_retryable

    def get_delay_ms(self, order_id: str) -> int:
        current_count = self._retry_counts.get(order_id, 0)

        delay = self._config.initial_delay_ms * (
            self._config.backoff_multiplier ** current_count
        )

        return min(int(delay), self._config.max_delay_ms)

    async def register_retry(self, order_id: str) -> int:
        async with self._lock:
            self._retry_counts[order_id] = self._retry_counts.get(order_id, 0) + 1
            delay_ms = self.get_delay_ms(order_id)
            self._pending_retries[order_id] = time.time() + delay_ms / 1000
            return self._retry_counts[order_id]

    async def clear_retry(self, order_id: str) -> None:
        async with self._lock:
            self._retry_counts.pop(order_id, None)
            self._pending_retries.pop(order_id, None)

    def get_retry_count(self, order_id: str) -> int:
        return self._retry_counts.get(order_id, 0)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_retries": sum(self._retry_counts.values()),
            "pending_retries": len(self._pending_retries),
            "config": {
                "max_retries": self._config.max_retries,
                "initial_delay_ms": self._config.initial_delay_ms,
                "max_delay_ms": self._config.max_delay_ms,
            },
        }


class OrderStateMachine:
    def __init__(
        self,
        journal: Optional[OrderJournal] = None,
        idempotency: Optional[IdempotencyManager] = None,
        retry_engine: Optional[RetryEngine] = None,
    ):
        self._journal = journal or OrderJournal()
        self._idempotency = idempotency or IdempotencyManager()
        self._retry_engine = retry_engine or RetryEngine()

        self._orders: Dict[str, Order] = {}
        self._state_change_callbacks: List[Callable[[Order, OrderStatus, OrderStatus], Awaitable[None]]] = []
        self._lock = asyncio.Lock()

    def register_state_change_callback(
        self,
        callback: Callable[[Order, OrderStatus, OrderStatus], Awaitable[None]],
    ) -> None:
        self._state_change_callbacks.append(callback)

    async def create_order(
        self,
        order: Order,
        idempotency_key: Optional[str] = None,
    ) -> Order:
        async with self._lock:
            if idempotency_key:
                if await self._idempotency.is_processed(idempotency_key):
                    existing_id = await self._idempotency.get_order_id(idempotency_key)
                    if existing_id and existing_id in self._orders:
                        logger.info(f"Returning existing order for idempotency key: {idempotency_key}")
                        return self._orders[existing_id]

                await self._idempotency.register(idempotency_key, order.order_id)
                order.metadata["idempotency_key"] = idempotency_key

            order.status = OrderStatus.PENDING
            order.created_at = datetime.now()
            order.updated_at = datetime.now()

            self._orders[order.order_id] = order

            self._journal.append(OrderJournalEntry(
                order_id=order.order_id,
                event=OrderEvent.CREATED,
                timestamp=time.time(),
                state_before=OrderStatus.PENDING,
                state_after=OrderStatus.PENDING,
                data=order.to_dict(),
                idempotency_key=idempotency_key,
            ))

            logger.info(f"Order created: {order.order_id} ({order.symbol} {order.side.value} {order.quantity})")

            return order

    async def transition(
        self,
        order_id: str,
        new_state: OrderStatus,
        event: OrderEvent,
        data: Optional[Dict[str, Any]] = None,
    ) -> Order:
        async with self._lock:
            order = self._orders.get(order_id)
            if not order:
                raise ValueError(f"Order not found: {order_id}")

            if order.status in TERMINAL_STATES:
                raise ValueError(
                    f"Cannot transition from terminal state: {order.status.value}"
                )

            if new_state not in VALID_TRANSITIONS.get(order.status, []):
                raise ValueError(
                    f"Invalid transition: {order.status.value} -> {new_state.value}"
                )

            old_state = order.status
            order.status = new_state
            order.updated_at = datetime.now()

            if data:
                if "filled_quantity" in data:
                    order.filled_quantity = data["filled_quantity"]
                if "average_price" in data:
                    order.average_price = data["average_price"]
                if "exchange_order_id" in data:
                    order.exchange_order_id = data["exchange_order_id"]
                if "error" in data:
                    order.error = data["error"]
                order.metadata.update(data)

            self._journal.append(OrderJournalEntry(
                order_id=order_id,
                event=event,
                timestamp=time.time(),
                state_before=old_state,
                state_after=new_state,
                data=data or {},
            ))

            idempotency_key = order.metadata.get("idempotency_key")
            if idempotency_key:
                if new_state in TERMINAL_STATES:
                    status = "completed" if new_state == OrderStatus.FILLED else "failed"
                    await self._idempotency.update_status(idempotency_key, status)

            logger.info(
                f"Order state change: {order_id} {old_state.value} -> {new_state.value} "
                f"({event.value})"
            )

        for callback in self._state_change_callbacks:
            try:
                await callback(order, old_state, new_state)
            except Exception as e:
                logger.error(f"State change callback error: {e}")

        return order

    async def submit(self, order_id: str) -> Order:
        return await self.transition(
            order_id,
            OrderStatus.SUBMITTED,
            OrderEvent.SUBMITTED,
        )

    async def partial_fill(
        self,
        order_id: str,
        filled_quantity: float,
        average_price: float,
    ) -> Order:
        return await self.transition(
            order_id,
            OrderStatus.PARTIALLY_FILLED,
            OrderEvent.PARTIAL_FILL,
            {
                "filled_quantity": filled_quantity,
                "average_price": average_price,
            },
        )

    async def fill(
        self,
        order_id: str,
        filled_quantity: float,
        average_price: float,
    ) -> Order:
        order = self._orders.get(order_id)
        if not order:
            raise ValueError(f"Order not found: {order_id}")

        if order.status == OrderStatus.PARTIALLY_FILLED:
            return await self.transition(
                order_id,
                OrderStatus.FILLED,
                OrderEvent.FILLED,
                {
                    "filled_quantity": filled_quantity,
                    "average_price": average_price,
                },
            )
        else:
            return await self.transition(
                order_id,
                OrderStatus.FILLED,
                OrderEvent.FILLED,
                {
                    "filled_quantity": filled_quantity,
                    "average_price": average_price,
                },
            )

    async def cancel(self, order_id: str) -> Order:
        order = self._orders.get(order_id)
        if not order:
            raise ValueError(f"Order not found: {order_id}")

        return await self.transition(
            order_id,
            OrderStatus.CANCELLED,
            OrderEvent.CANCELLED,
        )

    async def reject(self, order_id: str, reason: str) -> Order:
        return await self.transition(
            order_id,
            OrderStatus.REJECTED,
            OrderEvent.REJECTED,
            {"error": reason},
        )

    async def fail(self, order_id: str, error: str) -> Order:
        order = self._orders.get(order_id)
        if not order:
            raise ValueError(f"Order not found: {order_id}")

        if self._retry_engine.should_retry(order_id, error):
            retry_count = await self._retry_engine.register_retry(order_id)
            delay_ms = self._retry_engine.get_delay_ms(order_id)

            logger.info(
                f"Scheduling retry {retry_count} for order {order_id} "
                f"in {delay_ms}ms"
            )

            return await self.transition(
                order_id,
                OrderStatus.PENDING,
                OrderEvent.RETRY,
                {
                    "error": error,
                    "retry_count": retry_count,
                    "retry_delay_ms": delay_ms,
                },
            )
        else:
            return await self.transition(
                order_id,
                OrderStatus.FAILED,
                OrderEvent.FAILED,
                {"error": error},
            )

    async def reconcile(
        self,
        order_id: str,
        exchange_status: OrderStatus,
        filled_quantity: float,
        average_price: float,
    ) -> Order:
        order = self._orders.get(order_id)
        if not order:
            raise ValueError(f"Order not found: {order_id}")

        if order.status != exchange_status:
            logger.info(
                f"Reconciling order {order_id}: {order.status.value} -> "
                f"{exchange_status.value}"
            )

            if exchange_status == OrderStatus.FILLED:
                return await self.fill(order_id, filled_quantity, average_price)
            elif exchange_status == OrderStatus.PARTIALLY_FILLED:
                return await self.partial_fill(order_id, filled_quantity, average_price)
            elif exchange_status == OrderStatus.CANCELLED:
                return await self.cancel(order_id)
            elif exchange_status == OrderStatus.REJECTED:
                return await self.reject(order_id, "Exchange rejected")

        return order

    def get_order(self, order_id: str) -> Optional[Order]:
        return self._orders.get(order_id)

    def get_orders_by_state(self, state: OrderStatus) -> List[Order]:
        return [
            order for order in self._orders.values()
            if order.status == state
        ]

    def get_pending_orders(self) -> List[Order]:
        return self.get_orders_by_state(OrderStatus.PENDING)

    def get_active_orders(self) -> List[Order]:
        active_states = {
            OrderStatus.PENDING,
            OrderStatus.SUBMITTED,
            OrderStatus.PARTIALLY_FILLED,
        }
        return [
            order for order in self._orders.values()
            if order.status in active_states
        ]

    def is_terminal(self, order_id: str) -> bool:
        order = self._orders.get(order_id)
        return order.status in TERMINAL_STATES if order else True

    def get_history(self, order_id: str) -> List[OrderJournalEntry]:
        return self._journal.get_history(order_id)

    def get_stats(self) -> Dict[str, Any]:
        state_counts = {}
        for state in OrderStatus:
            state_counts[state.value] = len(self.get_orders_by_state(state))

        return {
            "total_orders": len(self._orders),
            "state_counts": state_counts,
            "active_orders": len(self.get_active_orders()),
            "journal_stats": self._journal.get_stats(),
            "idempotency_stats": self._idempotency.get_stats(),
            "retry_stats": self._retry_engine.get_stats(),
        }
