"""
Fill Sync Manager

成交同步管理器
处理 WebSocket 实时成交更新
"""

import asyncio
from typing import Dict, List, Callable, Optional
from datetime import datetime

from domain.execution.models import Order, OrderStatus
from services.execution_service.adapters.base import BaseExchangeAdapter
from services.execution_service.engine.order_manager import OrderManager
from services.execution_service.engine.position_manager import PositionManager
from infrastructure.logging import get_logger

logger = get_logger("execution_service.fill_sync")


class FillSyncManager:
    """成交同步管理器

    负责：
    - 注册 WebSocket 回调
    - 同步订单状态
    - 同步持仓状态
    - 发布成交事件
    """

    def __init__(
        self,
        order_manager: Optional[OrderManager] = None,
        position_manager: Optional[PositionManager] = None,
        db_manager=None,
    ):
        self._fill_callbacks: Dict[str, Callable] = {}
        self._position_callbacks: List[Callable] = []
        self._order_status_callbacks: List[Callable] = []
        self._running = False
        self._sync_tasks: List[asyncio.Task] = []
        self._order_manager = order_manager
        self._position_manager = position_manager
        self._db_manager = db_manager

    def set_managers(
        self,
        order_manager: OrderManager,
        position_manager: PositionManager,
        db_manager=None,
    ) -> None:
        """设置管理器（用于延迟初始化）"""
        self._order_manager = order_manager
        self._position_manager = position_manager
        self._db_manager = db_manager

    def register_adapter(self, adapter: BaseExchangeAdapter) -> None:
        """注册适配器并设置回调"""
        if hasattr(adapter, "on_fill"):
            adapter.on_fill(self._on_fill)

    async def _on_fill(
        self,
        order: Order,
        old_status: OrderStatus,
        new_status: OrderStatus,
    ) -> None:
        """处理成交回调"""
        logger.info(f"Fill sync: order {order.order_id} {old_status.value} -> {new_status.value}")

        # 更新内存中的订单
        if self._order_manager:
            if self._order_manager.get_order(order.order_id):
                self._order_manager.update_order_status(
                    order.order_id,
                    new_status,
                    order.filled_quantity,
                    order.average_price,
                )
            else:
                # 如果内存中没有这个订单，直接存入
                self._order_manager._orders[order.order_id] = order

        # 更新内存中的持仓
        if self._position_manager and new_status == OrderStatus.FILLED:
            self._position_manager.update_position(
                order=order,
                fill_price=order.average_price,
                fill_quantity=order.filled_quantity,
            )

        # 更新 ORM 存储
        if self._db_manager:
            await self._persist_from_fill(order)

        # 调用自定义回调
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
        """从成交回调持久化到数据库"""
        try:
            async with self._db_manager.session() as session:
                from services.execution_service.storage.orm_order_repository import ORMOrderRepository
                from services.execution_service.storage.orm_position_repository import ORMPositionRepository

                # 持久化订单
                order_repo = ORMOrderRepository(session)
                await order_repo.save(order)

                # 持久化持仓
                if self._position_manager:
                    position = self._position_manager.get_position(
                        order.symbol,
                        order.exchange,
                        getattr(order, "market_type", "spot"),
                    )
                    if position:
                        pos_repo = ORMPositionRepository(session)
                        await pos_repo.save(position)

        except Exception as e:
            logger.error(f"Failed to persist from fill: {e}")

    def on_fill(self, symbol: str, callback: Callable) -> None:
        """注册成交回调"""
        self._fill_callbacks[symbol] = callback

    def on_position_update(self, callback: Callable) -> None:
        """注册持仓更新回调"""
        self._position_callbacks.append(callback)

    def on_order_status_update(self, callback: Callable) -> None:
        """注册订单状态更新回调"""
        self._order_status_callbacks.append(callback)

    async def start(self) -> None:
        """启动同步"""
        self._running = True
        logger.info("Fill sync manager started")

    async def stop(self) -> None:
        """停止同步"""
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
        """获取活跃回调统计"""
        return {
            "fill_callbacks": len(self._fill_callbacks),
            "position_callbacks": len(self._position_callbacks),
            "order_status_callbacks": len(self._order_status_callbacks),
        }