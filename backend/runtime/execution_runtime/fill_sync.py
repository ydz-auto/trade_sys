import asyncio
from typing import Dict, List, Callable, Optional
from datetime import datetime

from domain.execution.models import Order, OrderStatus
from engines.adapters.exchange.base_adapter import BaseExchangeAdapter
from runtime.execution_runtime.engine.order_manager import OrderManager
from runtime.execution_runtime.publishers.order_publisher import OrderPublisher
from infrastructure.logging import get_logger

logger = get_logger("execution_service.fill_sync")


class FillSyncManager:
    """
    成交同步管理器

    职责：
    - 从交易所适配器接收订单状态更新
    - 更新本地订单状态
    - 发布 OrderFilled 事件（当订单成交时）
    - 不直接管理持仓（由 PortfolioRuntime 负责）
    """

    def __init__(
        self,
        order_manager: Optional[OrderManager] = None,
        position_manager=None,  # 保留参数但不使用，为了向后兼容
        db_manager=None,
    ):
        self._fill_callbacks: Dict[str, Callable] = {}
        self._position_callbacks: List[Callable] = []
        self._order_status_callbacks: List[Callable] = []
        self._running = False
        self._sync_tasks: List[asyncio.Task] = []
        self._order_manager = order_manager
        self._db_manager = db_manager
        self._order_publisher = OrderPublisher()

    def set_managers(
        self,
        order_manager: OrderManager,
        position_manager=None,  # 忽略 position manager
        db_manager=None,
    ) -> None:
        self._order_manager = order_manager
        self._db_manager = db_manager

    def register_adapter(self, adapter: BaseExchangeAdapter) -> None:
        if hasattr(adapter, "on_fill"):
            adapter.on_fill(self._on_fill)

    async def _on_fill(
        self,
        order: Order,
        old_status: OrderStatus,
        new_status: OrderStatus,
    ) -> None:
        logger.info(f"Fill sync: order {order.order_id} {old_status.value} -> {new_status.value}")

        if self._order_manager:
            if self._order_manager.get_order(order.order_id):
                self._order_manager.update_order_status(
                    order.order_id,
                    new_status,
                    order.filled_quantity,
                    order.average_price,
                )
            else:
                self._order_manager._orders[order.order_id] = order

        # 当订单成交时，发布 OrderFilled 事件，让 PortfolioRuntime 更新持仓
        if new_status == OrderStatus.FILLED:
            try:
                await self._order_publisher.publish_order_filled(
                    order=order,
                    fill_quantity=order.filled_quantity,
                    fill_price=order.average_price,
                )
            except Exception as e:
                logger.error(f"Failed to publish order_filled from fill sync: {e}")

        if self._db_manager:
            await self._persist_from_fill(order)

        for callback in self._order_status_callbacks:
            try:
                await callback(order, old_status, new_status)
            except Exception as e:
                logger.error(f"Order status callback error: {e}")

        if new_status == OrderStatus.FILLED:
            for callback in self._fill_callbacks.values():
                try:
                    await callback(order)
                except Exception as e:
                    logger.error(f"Fill callback error: {e}")

    async def _persist_from_fill(self, order: Order) -> None:
        """只保存订单，不保存持仓（持仓由 PortfolioRuntime 负责）"""
        try:
            async with self._db_manager.session() as session:
                from runtime.execution_runtime.storage.orm_order_repository import ORMOrderRepository

                order_repo = ORMOrderRepository(session)
                await order_repo.save(order)

        except Exception as e:
            logger.error(f"Failed to persist from fill: {e}")

    def on_fill(self, symbol: str, callback: Callable) -> None:
        self._fill_callbacks[symbol] = callback

    def on_position_update(self, callback: Callable) -> None:
        self._position_callbacks.append(callback)

    def on_order_status_update(self, callback: Callable) -> None:
        self._order_status_callbacks.append(callback)

    async def start(self) -> None:
        self._running = True
        logger.info("Fill sync manager started")

    async def stop(self) -> None:
        self._running = False
        for task in self._sync_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._sync_tasks.clear()
        logger.info("Fill sync manager stopped")

    def get_active_callbacks(self) -> Dict:
        return {
            "fill_callbacks": len(self._fill_callbacks),
            "position_callbacks": len(self._position_callbacks),
            "order_status_callbacks": len(self._order_status_callbacks),
        }
