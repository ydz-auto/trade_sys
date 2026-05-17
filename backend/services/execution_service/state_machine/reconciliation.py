"""
Order Reconciliation - 交易所状态同步

定期与交易所同步订单状态，确保本地状态与交易所一致:
- 检测状态不一致
- 自动修复差异
- 处理孤儿订单
- 滑点追踪
"""

import asyncio
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Callable, Awaitable
from datetime import datetime
import time

from domain.execution.models.enums import OrderStatus
from domain.execution.models.order import Order
from infrastructure.logging import get_logger

logger = get_logger("execution.reconciliation")


@dataclass
class ReconciliationResult:
    order_id: str
    local_state: OrderStatus
    exchange_state: OrderStatus
    reconciled: bool
    filled_quantity: float = 0.0
    average_price: float = 0.0
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "local_state": self.local_state.value,
            "exchange_state": self.exchange_state.value,
            "reconciled": self.reconciled,
            "filled_quantity": self.filled_quantity,
            "average_price": self.average_price,
            "error": self.error,
        }


@dataclass
class SlippageRecord:
    order_id: str
    symbol: str
    side: str
    expected_price: float
    actual_price: float
    quantity: float
    slippage_pct: float
    slippage_value: float
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side,
            "expected_price": self.expected_price,
            "actual_price": self.actual_price,
            "quantity": self.quantity,
            "slippage_pct": self.slippage_pct,
            "slippage_value": self.slippage_value,
            "timestamp": self.timestamp,
        }


@dataclass
class ReconciliationConfig:
    interval_seconds: float = 30.0
    max_age_seconds: float = 3600.0
    batch_size: int = 50
    enable_auto_fix: bool = True
    slippage_threshold_pct: float = 1.0


class SlippageTracker:
    def __init__(self, max_records: int = 10000):
        self._records: List[SlippageRecord] = []
        self._max_records = max_records
        self._by_symbol: Dict[str, List[SlippageRecord]] = {}
    
    def record(
        self,
        order_id: str,
        symbol: str,
        side: str,
        expected_price: float,
        actual_price: float,
        quantity: float,
    ) -> SlippageRecord:
        if expected_price > 0:
            slippage_pct = abs(actual_price - expected_price) / expected_price * 100
        else:
            slippage_pct = 0.0
        
        slippage_value = abs(actual_price - expected_price) * quantity
        
        record = SlippageRecord(
            order_id=order_id,
            symbol=symbol,
            side=side,
            expected_price=expected_price,
            actual_price=actual_price,
            quantity=quantity,
            slippage_pct=slippage_pct,
            slippage_value=slippage_value,
        )
        
        self._records.append(record)
        
        if symbol not in self._by_symbol:
            self._by_symbol[symbol] = []
        self._by_symbol[symbol].append(record)
        
        if len(self._records) > self._max_records:
            removed = self._records.pop(0)
            if removed.symbol in self._by_symbol:
                self._by_symbol[removed.symbol] = [
                    r for r in self._by_symbol[removed.symbol]
                    if r.order_id != removed.order_id
                ]
        
        if slippage_pct > 1.0:
            logger.warning(
                f"High slippage detected: {order_id} {symbol} "
                f"expected={expected_price} actual={actual_price} "
                f"slippage={slippage_pct:.2f}%"
            )
        
        return record
    
    def get_stats(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        records = self._by_symbol.get(symbol, []) if symbol else self._records
        
        if not records:
            return {
                "total_trades": 0,
                "avg_slippage_pct": 0.0,
                "max_slippage_pct": 0.0,
                "total_slippage_value": 0.0,
            }
        
        slippages = [r.slippage_pct for r in records]
        
        return {
            "total_trades": len(records),
            "avg_slippage_pct": sum(slippages) / len(slippages),
            "max_slippage_pct": max(slippages),
            "total_slippage_value": sum(r.slippage_value for r in records),
        }
    
    def get_records(self, limit: int = 100) -> List[SlippageRecord]:
        return self._records[-limit:]


class OrderReconciliation:
    def __init__(
        self,
        state_machine,
        config: ReconciliationConfig = ReconciliationConfig(),
    ):
        self._state_machine = state_machine
        self._config = config
        self._slippage_tracker = SlippageTracker()
        
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
        self._exchange_adapters: Dict[str, Any] = {}
        
        self._stats = {
            "total_reconciliations": 0,
            "successful_reconciliations": 0,
            "failed_reconciliations": 0,
            "state_mismatches": 0,
            "orphan_orders": 0,
        }
    
    def register_exchange_adapter(self, exchange: str, adapter: Any) -> None:
        self._exchange_adapters[exchange] = adapter
        logger.info(f"Registered exchange adapter: {exchange}")
    
    async def start(self) -> None:
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._reconciliation_loop())
        logger.info("Order reconciliation started")
    
    async def stop(self) -> None:
        if not self._running:
            return
        
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("Order reconciliation stopped")
    
    async def _reconciliation_loop(self) -> None:
        while self._running:
            try:
                await self.reconcile_all()
            except Exception as e:
                logger.error(f"Reconciliation loop error: {e}")
            
            await asyncio.sleep(self._config.interval_seconds)
    
    async def reconcile_all(self) -> List[ReconciliationResult]:
        active_orders = self._state_machine.get_active_orders()
        
        if not active_orders:
            return []
        
        results = []
        
        for i in range(0, len(active_orders), self._config.batch_size):
            batch = active_orders[i:i + self._config.batch_size]
            
            batch_results = await asyncio.gather(
                *[self.reconcile_order(order) for order in batch],
                return_exceptions=True,
            )
            
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Reconciliation error: {result}")
                else:
                    results.append(result)
        
        self._stats["total_reconciliations"] += 1
        
        return results
    
    async def reconcile_order(self, order: Order) -> ReconciliationResult:
        adapter = self._exchange_adapters.get(order.exchange.value)
        
        if not adapter:
            return ReconciliationResult(
                order_id=order.order_id,
                local_state=order.status,
                exchange_state=order.status,
                reconciled=False,
                error=f"No adapter for exchange: {order.exchange.value}",
            )
        
        try:
            if not order.exchange_order_id:
                return ReconciliationResult(
                    order_id=order.order_id,
                    local_state=order.status,
                    exchange_state=order.status,
                    reconciled=True,
                )
            
            exchange_order = await adapter.get_order(order.exchange_order_id)
            
            if not exchange_order:
                self._stats["orphan_orders"] += 1
                return ReconciliationResult(
                    order_id=order.order_id,
                    local_state=order.status,
                    exchange_state=OrderStatus.CANCELLED,
                    reconciled=False,
                    error="Order not found on exchange",
                )
            
            exchange_status = self._map_exchange_status(exchange_order.get("status", ""))
            filled_quantity = float(exchange_order.get("filledQty", 0))
            average_price = float(exchange_order.get("avgPrice", 0))
            
            if order.status != exchange_status:
                self._stats["state_mismatches"] += 1
                logger.warning(
                    f"State mismatch for {order.order_id}: "
                    f"local={order.status.value} exchange={exchange_status.value}"
                )
                
                if self._config.enable_auto_fix:
                    await self._state_machine.reconcile(
                        order.order_id,
                        exchange_status,
                        filled_quantity,
                        average_price,
                    )
                    
                    if exchange_status == OrderStatus.FILLED and order.price:
                        self._slippage_tracker.record(
                            order_id=order.order_id,
                            symbol=order.symbol,
                            side=order.side.value,
                            expected_price=order.price,
                            actual_price=average_price,
                            quantity=filled_quantity,
                        )
                    
                    self._stats["successful_reconciliations"] += 1
                    
                    return ReconciliationResult(
                        order_id=order.order_id,
                        local_state=order.status,
                        exchange_state=exchange_status,
                        reconciled=True,
                        filled_quantity=filled_quantity,
                        average_price=average_price,
                    )
            
            return ReconciliationResult(
                order_id=order.order_id,
                local_state=order.status,
                exchange_state=exchange_status,
                reconciled=True,
                filled_quantity=filled_quantity,
                average_price=average_price,
            )
            
        except Exception as e:
            self._stats["failed_reconciliations"] += 1
            logger.error(f"Failed to reconcile order {order.order_id}: {e}")
            
            return ReconciliationResult(
                order_id=order.order_id,
                local_state=order.status,
                exchange_state=order.status,
                reconciled=False,
                error=str(e),
            )
    
    def _map_exchange_status(self, exchange_status: str) -> OrderStatus:
        status_map = {
            "NEW": OrderStatus.SUBMITTED,
            "PARTIALLY_FILLED": OrderStatus.PARTIALLY_FILLED,
            "FILLED": OrderStatus.FILLED,
            "CANCELED": OrderStatus.CANCELLED,
            "CANCELLED": OrderStatus.CANCELLED,
            "REJECTED": OrderStatus.REJECTED,
            "EXPIRED": OrderStatus.EXPIRED,
            "PENDING": OrderStatus.PENDING,
            "OPEN": OrderStatus.SUBMITTED,
            "CLOSED": OrderStatus.FILLED,
        }
        
        return status_map.get(exchange_status.upper(), OrderStatus.SUBMITTED)
    
    async def detect_orphan_orders(self) -> List[Order]:
        active_orders = self._state_machine.get_active_orders()
        orphans = []
        
        for order in active_orders:
            if not order.exchange_order_id:
                age = time.time() - order.created_at.timestamp()
                if age > self._config.max_age_seconds:
                    orphans.append(order)
        
        if orphans:
            logger.warning(f"Detected {len(orphans)} orphan orders")
        
        return orphans
    
    async def cleanup_orphan_orders(self) -> int:
        orphans = await self.detect_orphan_orders()
        
        for order in orphans:
            try:
                await self._state_machine.fail(
                    order.order_id,
                    "Orphan order - no exchange order ID",
                )
            except Exception as e:
                logger.error(f"Failed to cleanup orphan {order.order_id}: {e}")
        
        return len(orphans)
    
    def get_slippage_stats(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        return self._slippage_tracker.get_stats(symbol)
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "config": {
                "interval_seconds": self._config.interval_seconds,
                "max_age_seconds": self._config.max_age_seconds,
                "batch_size": self._config.batch_size,
                "enable_auto_fix": self._config.enable_auto_fix,
            },
            "stats": self._stats,
            "slippage": self._slippage_tracker.get_stats(),
        }
