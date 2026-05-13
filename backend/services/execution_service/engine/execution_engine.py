"""
Execution Engine

执行引擎核心
"""

from typing import Dict, List, Optional, Union
import asyncio

from domain.execution.models import (
    Order,
    OrderRequest,
    OrderResult,
    OrderIntent,
    Position,
    Exchange,
    OrderSide,
    OrderType,
    OrderStatus,
    MarketType,
)
from domain.execution.config import ExecutionRuntimeConfig
from services.execution_service.adapters.base import BaseExchangeAdapter
from services.execution_service.engine.order_manager import OrderManager
from services.execution_service.engine.position_manager import PositionManager
from services.execution_service.fill_sync import FillSyncManager
from services.execution_service.storage.orm_order_repository import ORMOrderRepository
from services.execution_service.storage.orm_position_repository import ORMPositionRepository
from services.execution_service.publishers.order_publisher import OrderPublisher
from infrastructure.logging import get_logger
from infrastructure.database.session import DatabaseSessionManager, get_db_manager

logger = get_logger("execution_service.engine")


class ExecutionEngine:
    """执行引擎

    统一管理所有交易所的订单执行

    支持双存储模式：
    - 内存存储（默认）- 用于开发测试
    - PostgreSQL ORM - 用于生产环境
    """

    def __init__(
        self,
        config: ExecutionRuntimeConfig = None,
        use_orm: bool = False,
        db_manager: Optional[DatabaseSessionManager] = None,
    ):
        self.config = config or ExecutionRuntimeConfig()
        self._use_orm = use_orm
        self._adapters: Dict[Exchange, BaseExchangeAdapter] = {}
        self._order_manager = OrderManager()
        self._position_manager = PositionManager()
        self._fill_sync = FillSyncManager()

        self._db_manager = db_manager
        self._order_repo: Optional[ORMOrderRepository] = None
        self._position_repo: Optional[ORMPositionRepository] = None

        # 事件发布器
        self._order_publisher = OrderPublisher()

        if self._use_orm:
            if not self._db_manager:
                self._db_manager = get_db_manager()
            logger.info("ORM storage enabled")

        # 初始化 FillSyncManager 的管理器引用
        self._fill_sync.set_managers(
            self._order_manager,
            self._position_manager,
            self._db_manager if self._use_orm else None,
        )

    def register_adapter(self, adapter: BaseExchangeAdapter) -> None:
        """注册交易所适配器"""
        self._adapters[adapter.exchange] = adapter
        self._fill_sync.register_adapter(adapter)
        logger.info(f"Registered adapter: {adapter.exchange.value}")

    def get_adapter(self, exchange: Exchange) -> Optional[BaseExchangeAdapter]:
        """获取适配器"""
        return self._adapters.get(exchange)

    async def connect_all(self) -> Dict[Exchange, bool]:
        """连接所有交易所"""
        results = {}
        for exchange, adapter in self._adapters.items():
            try:
                results[exchange] = await adapter.connect()
            except Exception as e:
                logger.error(f"Failed to connect {exchange.value}: {e}")
                results[exchange] = False

        if any(results.values()):
            await self._fill_sync.start()

        return results

    async def disconnect_all(self) -> None:
        """断开所有连接"""
        await self._fill_sync.stop()
        for adapter in self._adapters.values():
            try:
                await adapter.disconnect()
            except Exception as e:
                logger.error(f"Failed to disconnect: {e}")

    async def execute_order(self, request: OrderRequest) -> OrderResult:
        """执行订单

        完整的订单执行流程：
        1. 创建订单记录
        2. 提交到交易所
        3. 更新订单状态
        4. 更新持仓
        5. 发布事件
        """
        exchange = request.exchange

        if exchange not in self._adapters:
            return OrderResult(success=False, error=f"Exchange {exchange.value} not registered")

        adapter = self._adapters[exchange]

        if not adapter.is_connected():
            return OrderResult(success=False, error=f"Exchange {exchange.value} not connected")

        if hasattr(adapter, "set_leverage") and request.leverage > 1:
            symbol = request.symbol.upper().replace("/", "")
            await adapter.set_leverage(symbol, request.leverage)

        order = self._order_manager.create_order(request)
        self._order_manager.update_order_status(order.order_id, OrderStatus.SUBMITTED)

        if self._use_orm:
            await self._persist_order(order)

        # 发布订单创建事件
        try:
            await self._order_publisher.publish_order_created(order)
        except Exception as e:
            logger.error(f"Failed to publish order_created event: {e}")

        result = await adapter.create_order(request)

        if result.success and result.order:
            self._order_manager.update_order_status(
                order.order_id,
                result.order.status,
                result.order.filled_quantity,
                result.order.average_price,
            )

            if result.order.status == OrderStatus.FILLED:
                self._position_manager.update_position(
                    order=result.order,
                    fill_price=result.order.average_price,
                    fill_quantity=result.order.filled_quantity,
                )
                if self._use_orm:
                    await self._persist_position(result.order)

                # 发布成交事件
                try:
                    await self._order_publisher.publish_order_filled(
                        order=result.order,
                        fill_quantity=result.order.filled_quantity,
                        fill_price=result.order.average_price,
                    )
                except Exception as e:
                    logger.error(f"Failed to publish order_filled event: {e}")

            order = self._order_manager.get_order(order.order_id)
            if self._use_orm:
                await self._persist_order(order)

            # 发布订单更新事件
            try:
                await self._order_publisher.publish_order_updated(
                    order=order,
                    old_status=OrderStatus.SUBMITTED,
                    new_status=order.status,
                )
            except Exception as e:
                logger.error(f"Failed to publish order_updated event: {e}")

            return OrderResult(success=True, order=order)
        else:
            self._order_manager.update_order_status(
                order.order_id,
                OrderStatus.FAILED,
                error=result.error,
            )
            if self._use_orm:
                order = self._order_manager.get_order(order.order_id)
                await self._persist_order(order)

            return OrderResult(success=False, error=result.error)

    async def execute_intent(self, intent: OrderIntent) -> OrderResult:
        """执行订单意图"""
        request = intent.to_order_request(order_type=OrderType.MARKET)
        return await self.execute_order(request)

    async def execute_futures_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: Optional[float] = None,
        leverage: int = 1,
        reduce_only: bool = False,
        exchange: Exchange = Exchange.BINANCE,
        order_type: OrderType = OrderType.MARKET,
    ) -> OrderResult:
        """执行合约订单"""
        request = OrderRequest(
            symbol=symbol,
            exchange=exchange,
            side=OrderSide(side.lower()),
            order_type=order_type,
            quantity=quantity,
            price=price,
            market_type=MarketType.USDT_FUTURES,
            leverage=leverage,
            reduce_only=reduce_only,
        )
        return await self.execute_order(request)

    async def close_position(
        self,
        symbol: str,
        exchange: Exchange = Exchange.BINANCE,
        market_type: MarketType = MarketType.USDT_FUTURES,
    ) -> OrderResult:
        """平仓"""
        position = self._position_manager.get_position(symbol, exchange, market_type)
        if not position or position.quantity == 0:
            return OrderResult(success=False, error="No open position")

        side = OrderSide.SELL if position.quantity > 0 else OrderSide.BUY
        quantity = abs(position.quantity)

        request = OrderRequest(
            symbol=symbol,
            exchange=exchange,
            side=side,
            order_type=OrderType.MARKET,
            quantity=quantity,
            market_type=market_type,
            leverage=position.leverage,
            reduce_only=True,
        )
        return await self.execute_order(request)

    async def _persist_order(self, order: Order) -> None:
        """持久化订单到数据库"""
        if not self._use_orm or not self._db_manager:
            return
        try:
            async with self._db_manager.session() as session:
                repo = ORMOrderRepository(session)
                await repo.save(order)
        except Exception as e:
            logger.error(f"Failed to persist order: {e}")

    async def _persist_position(self, order: Order) -> None:
        """持久化持仓到数据库"""
        if not self._use_orm or not self._db_manager:
            return
        try:
            position = self._position_manager.get_position(
                order.symbol,
                order.exchange,
                getattr(order, "market_type", "spot"),
            )
            if position:
                async with self._db_manager.session() as session:
                    repo = ORMPositionRepository(session)
                    await repo.save(position)
        except Exception as e:
            logger.error(f"Failed to persist position: {e}")

    async def load_from_db(self) -> None:
        """从数据库加载历史数据"""
        if not self._use_orm or not self._db_manager:
            return

        logger.info("Loading data from database...")

        try:
            async with self._db_manager.session() as session:
                order_repo = ORMOrderRepository(session)
                position_repo = ORMPositionRepository(session)

                db_orders = await order_repo.list_recent(limit=1000)
                for db_order in db_orders:
                    order = order_repo.to_domain_model(db_order)
                    if not self._order_manager.get_order(order.order_id):
                        self._order_manager._orders[order.order_id] = order
                logger.info(f"Loaded {len(db_orders)} orders from DB")

                db_positions = await position_repo.list_all()
                for db_position in db_positions:
                    pos = position_repo.to_domain_model(db_position)
                    key = (pos.symbol, pos.exchange, pos.market_type)
                    self._position_manager._positions[key] = pos
                logger.info(f"Loaded {len(db_positions)} positions from DB")
        except Exception as e:
            logger.error(f"Failed to load from DB: {e}")

    async def save_all_to_db(self) -> None:
        """保存所有数据到数据库"""
        if not self._use_orm or not self._db_manager:
            return

        try:
            async with self._db_manager.session() as session:
                order_repo = ORMOrderRepository(session)
                position_repo = ORMPositionRepository(session)

                for order in self._order_manager.get_order_history():
                    await order_repo.save(order)

                for pos in self._position_manager.get_all_positions():
                    await position_repo.save(pos)

                logger.info("All data saved to DB")
        except Exception as e:
            logger.error(f"Failed to save to DB: {e}")

    def get_order(self, order_id: str) -> Optional[Order]:
        """获取订单"""
        return self._order_manager.get_order(order_id)

    def get_order_history(self) -> List[Order]:
        """获取订单历史"""
        return self._order_manager.get_order_history()

    def get_position(self, symbol: str, exchange: Exchange, market_type: MarketType = MarketType.SPOT) -> Optional[Position]:
        """获取持仓"""
        return self._position_manager.get_position(symbol, exchange, market_type)

    def get_all_positions(self) -> List[Position]:
        """获取所有持仓"""
        return self._position_manager.get_all_positions()

    def get_local_positions(self) -> List[Position]:
        """获取本地持仓（别名，兼容旧代码）"""
        return self.get_all_positions()

    def on_fill(self, symbol: str, callback) -> None:
        """注册成交回调"""
        self._fill_sync.on_fill(symbol, callback)

    def on_position_update(self, callback) -> None:
        """注册持仓更新回调"""
        self._fill_sync.on_position_update(callback)


_execution_engine: Optional[ExecutionEngine] = None


def get_execution_engine(
    use_orm: bool = False,
    db_manager: Optional[DatabaseSessionManager] = None,
) -> ExecutionEngine:
    """获取执行引擎单例"""
    global _execution_engine
    if _execution_engine is None:
        _execution_engine = ExecutionEngine(
            use_orm=use_orm,
            db_manager=db_manager,
        )
    return _execution_engine


async def init_execution_engine(
    config: ExecutionRuntimeConfig = None,
    use_orm: bool = False,
    db_manager: Optional[DatabaseSessionManager] = None,
    load_from_db: bool = True,
) -> ExecutionEngine:
    """初始化执行引擎"""
    engine = get_execution_engine(
        use_orm=use_orm,
        db_manager=db_manager,
    )

    if config:
        engine.config = config

    if use_orm and load_from_db:
        await engine.load_from_db()

    return engine


def reset_execution_engine() -> None:
    """重置执行引擎（用于测试）"""
    global _execution_engine
    _execution_engine = None
