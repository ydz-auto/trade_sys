"""
Order Filled Event Consumer - 成交事件消费者

职责：
1. 消费 ExecutionRuntime 发布的 OrderFilled 事件
2. 更新 PortfolioRuntime 中的持仓状态
3. 确保持仓归属权清晰

架构：
    ExecutionRuntime
         ↓
    OrderFilled Event (Kafka)
         ↓
    OrderFilledConsumer
         ↓
    PortfolioRuntime
"""
from typing import Dict, Any, Optional
import asyncio

from infrastructure.logging import get_logger
from infrastructure.config.defaults.infrastructure.middleware import KAFKA_BOOTSTRAP_SERVERS
from infrastructure.messaging.runtime_consumer import RuntimeConsumer, ConsumerConfig

from runtime.portfolio_runtime.portfolio_projection import PortfolioProjection, get_portfolio_projection

logger = get_logger("portfolio_runtime.consumers.order_filled")


class OrderFilledConsumer:
    """
    成交事件消费者

    消费 execution.orders.filled 主题的消息，更新持仓
    """

    TOPIC = "execution.orders.filled"
    GROUP_ID = "portfolio-runtime-order-filled-consumer"

    def __init__(
        self,
        portfolio_projection: PortfolioProjection = None,
        bootstrap_servers: str = None,
    ):
        self._portfolio = portfolio_projection or get_portfolio_projection()
        self._bootstrap_servers = bootstrap_servers or KAFKA_BOOTSTRAP_SERVERS
        self._consumer: Optional[RuntimeConsumer] = None
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def initialize(self) -> None:
        """初始化消费者"""
        config = ConsumerConfig(
            bootstrap_servers=self._bootstrap_servers,
            topics=[self.TOPIC],
            group_id=self.GROUP_ID,
            auto_offset_reset="latest",
        )
        self._consumer = RuntimeConsumer(config)
        self._consumer.register_handler(self.TOPIC, self._handle_order_filled)
        logger.info(f"OrderFilledConsumer initialized for topic: {self.TOPIC}")

    async def start(self) -> None:
        """启动消费循环"""
        if not self._consumer:
            await self.initialize()

        self._running = True
        await self._consumer.start()
        self._task = asyncio.create_task(self._consumer.run())
        logger.info("OrderFilledConsumer started")

    async def stop(self) -> None:
        """停止消费者"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._consumer:
            await self._consumer.stop()
        logger.info("OrderFilledConsumer stopped")

    async def _handle_order_filled(self, message: Dict[str, Any]) -> None:
        """
        处理 OrderFilled 事件

        Args:
            message: Kafka 消息
        """
        try:
            event_data = message.get("value", {})
            if not event_data:
                return

            # 验证事件类型
            event_type = event_data.get("event_type")
            if event_type != "order_filled":
                logger.warning(f"Unexpected event type: {event_type}")
                return

            # 提取订单信息
            order_data = event_data.get("order", {})
            fill_quantity = event_data.get("fill_quantity", 0)
            fill_price = event_data.get("fill_price", 0)

            symbol = order_data.get("symbol", "")
            side = order_data.get("side", "buy")
            quantity = fill_quantity  # 使用成交数量而不是原始订单数量
            price = fill_price

            if not symbol or quantity <= 0 or price <= 0:
                logger.warning(f"Invalid fill event data: {event_data}")
                return

            logger.info(f"Processing fill event: {symbol} {side} {quantity} @ {price}")

            # 转换为 PortfolioProjection 需要的格式
            fill_event = {
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "price": price,
                "order_id": order_data.get("order_id"),
                "timestamp": event_data.get("timestamp"),
            }

            # 更新持仓
            await self._portfolio.process_fill(fill_event)

            logger.info(f"Position updated for {symbol}")

        except Exception as e:
            logger.error(f"Error handling order filled event: {e}", exc_info=True)


_order_filled_consumer: Optional[OrderFilledConsumer] = None


def get_order_filled_consumer() -> OrderFilledConsumer:
    """获取 OrderFilledConsumer 单例"""
    global _order_filled_consumer
    if _order_filled_consumer is None:
        _order_filled_consumer = OrderFilledConsumer()
    return _order_filled_consumer
