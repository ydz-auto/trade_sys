from typing import Dict, List, Optional, Union
import asyncio

from domain.execution.models import (
    Order,
    OrderRequest,
    OrderResult,
    OrderIntent,
    Exchange,
    OrderSide,
    OrderType,
    OrderStatus,
    MarketType,
)
from domain.execution.config import ExecutionRuntimeConfig
from engines.adapters.exchange.base_adapter import BaseExchangeAdapter
from runtime.execution_runtime.engine.order_manager import OrderManager
from runtime.execution_runtime.fill_sync import FillSyncManager
from runtime.execution_runtime.storage.orm_order_repository import ORMOrderRepository
from runtime.execution_runtime.publishers.order_publisher import OrderPublisher
from infrastructure.logging import get_logger
from infrastructure.persistence.database.session import DatabaseSessionManager, get_db_manager

logger = get_logger("execution_service.engine")


class ExecutionEngine:
    """
    Execution Engine - 执行引擎

    职责：
    - 订单生命周期管理（唯一 owner）
    - 调用交易所适配器执行订单
    - 发布订单事件（不直接管理持仓）

    不负责：
    - 持仓管理（由 PortfolioRuntime 负责）
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
        self._fill_sync = FillSyncManager()

        self._db_manager = db_manager
        self._order_repo: Optional[ORMOrderRepository] = None

        self._order_publisher = OrderPublisher()

        if self._use_orm:
            if not self._db_manager:
                self._db_manager = get_db_manager()
            logger.info("ORM storage enabled")

        self._fill_sync.set_managers(
            self._order_manager,
            None,  # PositionManager 已移除
            self._db_manager if self._use_orm else None,
        )

    def register_adapter(self, adapter: BaseExchangeAdapter) -> None:
        self._adapters[adapter.exchange] = adapter
        self._fill_sync.register_adapter(adapter)
        logger.info(f"Registered adapter: {adapter.exchange.value}")

    def get_adapter(self, exchange: Exchange) -> Optional[BaseExchangeAdapter]:
        return self._adapters.get(exchange)

    async def connect_all(self) -> Dict[Exchange, bool]:
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
        await self._fill_sync.stop()
        for adapter in self._adapters.values():
            try:
                await adapter.disconnect()
            except Exception as e:
                logger.error(f"Failed to disconnect: {e}")

    async def execute_order(self, request: OrderRequest) -> OrderResult:
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

        try:
            await self._order_publisher.publish_order_created(order)
        except Exception as e:
            logger.error(f"Failed to publish order_created event: {e}")

        result = await adapter.create_order(request)

        if result.success and result.order:
            # 同步 exchange_order_id 等所有字段
            local_order = self._order_manager.get_order(order.order_id)
            if local_order:
                if hasattr(result.order, 'exchange_order_id') and result.order.exchange_order_id:
                    local_order.exchange_order_id = result.order.exchange_order_id
                if hasattr(result.order, 'client_order_id') and result.order.client_order_id:
                    local_order.client_order_id = result.order.client_order_id
            
            self._order_manager.update_order_status(
                order.order_id,
                result.order.status,
                result.order.filled_quantity,
                result.order.average_price,
            )

            # 发布 OrderFilled 事件，让 PortfolioRuntime 更新持仓
            if result.order.status == OrderStatus.FILLED:
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
        if not self._use_orm or not self._db_manager:
            return
        try:
            async with self._db_manager.session() as session:
                repo = ORMOrderRepository(session)
                await repo.save(order)
        except Exception as e:
            logger.error(f"Failed to persist order: {e}")

    async def load_from_db(self) -> None:
        """只加载订单，不加载持仓（持仓由 PortfolioRuntime 负责）"""
        if not self._use_orm or not self._db_manager:
            return

        logger.info("Loading orders from database...")

        try:
            async with self._db_manager.session() as session:
                order_repo = ORMOrderRepository(session)

                db_orders = await order_repo.list_recent(limit=1000)
                for db_order in db_orders:
                    order = order_repo.to_domain_model(db_order)
                    if not self._order_manager.get_order(order.order_id):
                        self._order_manager._orders[order.order_id] = order
                logger.info(f"Loaded {len(db_orders)} orders from DB")
        except Exception as e:
            logger.error(f"Failed to load orders from DB: {e}")

    async def save_all_to_db(self) -> None:
        """只保存订单，不保存持仓（持仓由 PortfolioRuntime 负责）"""
        if not self._use_orm or not self._db_manager:
            return

        try:
            async with self._db_manager.session() as session:
                order_repo = ORMOrderRepository(session)

                for order in self._order_manager.get_order_history():
                    await order_repo.save(order)

                logger.info("Orders saved to DB")
        except Exception as e:
            logger.error(f"Failed to save orders to DB: {e}")

    def get_order(self, order_id: str) -> Optional[Order]:
        return self._order_manager.get_order(order_id)

    def get_order_history(self) -> List[Order]:
        return self._order_manager.get_order_history()

    def on_fill(self, symbol: str, callback) -> None:
        self._fill_sync.on_fill(symbol, callback)

    def on_position_update(self, callback) -> None:
        self._fill_sync.on_position_update(callback)


_execution_engine: Optional[ExecutionEngine] = None


def get_execution_engine(
    use_orm: bool = False,
    db_manager: Optional[DatabaseSessionManager] = None,
) -> ExecutionEngine:
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
    global _execution_engine
    _execution_engine = None
