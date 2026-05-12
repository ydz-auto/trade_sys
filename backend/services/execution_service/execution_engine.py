"""
Execution Service - 订单执行服务

功能：
- 交易所 API 对接（Binance/OKX）
- 订单管理（创建、查询、取消）
- 持仓管理
- 交易历史

架构：
Signal → ExecutionService → Exchange API → Order
"""

from enum import Enum
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from datetime import datetime
import asyncio

from infrastructure.logging import get_logger

logger = get_logger("execution_service")


class OrderSide(str, Enum):
    """订单方向"""
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """订单类型"""
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


class OrderStatus(str, Enum):
    """订单状态"""
    PENDING = "pending"
    SUBMITTED = "submitted"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    FAILED = "failed"


class Exchange(str, Enum):
    """交易所"""
    BINANCE = "binance"
    OKX = "okx"
    COINBASE = "coinbase"


@dataclass
class Order:
    """订单"""
    order_id: str
    symbol: str
    exchange: Exchange
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    average_price: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Position:
    """持仓"""
    symbol: str
    exchange: Exchange
    quantity: float
    average_price: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class OrderRequest:
    """订单请求"""
    symbol: str
    exchange: Exchange
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    client_order_id: Optional[str] = None


@dataclass
class OrderResult:
    """订单结果"""
    success: bool
    order: Optional[Order] = None
    error: Optional[str] = None


class BaseExchangeAdapter:
    """交易所适配器基类"""

    def __init__(self, exchange: Exchange):
        self.exchange = exchange

    async def connect(self) -> bool:
        """连接交易所"""
        raise NotImplementedError

    async def disconnect(self) -> None:
        """断开连接"""
        raise NotImplementedError

    async def create_order(self, request: OrderRequest) -> OrderResult:
        """创建订单"""
        raise NotImplementedError

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """取消订单"""
        raise NotImplementedError

    async def get_order(self, order_id: str, symbol: str) -> Optional[Order]:
        """查询订单"""
        raise NotImplementedError

    async def get_positions(self) -> List[Position]:
        """获取持仓"""
        raise NotImplementedError

    async def get_balance(self) -> Dict[str, float]:
        """获取余额"""
        raise NotImplementedError


class BinanceAdapter(BaseExchangeAdapter):
    """Binance 交易所适配器"""

    def __init__(self, api_key: str = None, api_secret: str = None, testnet: bool = True):
        super().__init__(Exchange.BINANCE)
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self._connected = False
        self._orders: Dict[str, Order] = {}
        self._positions: Dict[str, Position] = {}

    async def connect(self) -> bool:
        """连接 Binance"""
        if not self.api_key or not self.api_secret:
            logger.warning("Binance API credentials not provided, using mock mode")
            self._connected = True
            return True

        try:
            # 实际实现需要安装 ccxt
            # import ccxt
            # self._exchange = ccxt.binance({
            #     'apiKey': self.api_key,
            #     'secret': self.api_secret,
            #     'enableRateLimit': True,
            # })
            logger.info("Binance adapter connected (mock)")
            self._connected = True
            return True
        except Exception as e:
            logger.error(f"Failed to connect Binance: {e}")
            return False

    async def disconnect(self) -> None:
        """断开连接"""
        self._connected = False
        logger.info("Binance adapter disconnected")

    async def create_order(self, request: OrderRequest) -> OrderResult:
        """创建订单"""
        if not self._connected:
            return OrderResult(success=False, error="Not connected")

        try:
            order_id = f"binance_{int(datetime.now().timestamp() * 1000)}"

            order = Order(
                order_id=order_id,
                symbol=request.symbol,
                exchange=self.exchange,
                side=request.side,
                order_type=request.order_type,
                quantity=request.quantity,
                price=request.price,
                status=OrderStatus.SUBMITTED,
                metadata={"client_order_id": request.client_order_id}
            )

            self._orders[order_id] = order

            # 模拟成交（实际需要调用 Binance API）
            if request.order_type == OrderType.MARKET:
                order.status = OrderStatus.FILLED
                order.filled_quantity = order.quantity
                order.average_price = request.price or 50000.0  # 模拟价格
                self._update_position(order)

            logger.info(f"Order created: {order_id} {request.side} {request.quantity} {request.symbol}")
            return OrderResult(success=True, order=order)

        except Exception as e:
            logger.error(f"Failed to create order: {e}")
            return OrderResult(success=False, error=str(e))

    def _update_position(self, order: Order):
        """更新持仓"""
        symbol = order.symbol
        if symbol not in self._positions:
            self._positions[symbol] = Position(
                symbol=symbol,
                exchange=order.exchange,
                quantity=0,
                average_price=0
            )

        pos = self._positions[symbol]

        if order.side == OrderSide.BUY:
            total_cost = pos.quantity * pos.average_price + order.filled_quantity * order.average_price
            pos.quantity += order.filled_quantity
            pos.average_price = total_cost / pos.quantity if pos.quantity > 0 else 0
        else:
            pos.quantity -= order.filled_quantity

        if pos.quantity < 0.001:  # 小于最小精度视为平仓
            pos.quantity = 0
            pos.average_price = 0

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """取消订单"""
        if order_id in self._orders:
            order = self._orders[order_id]
            if order.status in [OrderStatus.PENDING, OrderStatus.SUBMITTED]:
                order.status = OrderStatus.CANCELLED
                logger.info(f"Order cancelled: {order_id}")
                return True
        return False

    async def get_order(self, order_id: str, symbol: str) -> Optional[Order]:
        """查询订单"""
        return self._orders.get(order_id)

    async def get_positions(self) -> List[Position]:
        """获取持仓"""
        return [p for p in self._positions.values() if p.quantity > 0]

    async def get_balance(self) -> Dict[str, float]:
        """获取余额"""
        return {
            "USDT": 10000.0,  # 模拟余额
            "BTC": 0.5,
            "ETH": 5.0,
        }


class ExecutionService:
    """执行服务

    统一管理所有交易所的订单执行
    """

    def __init__(self):
        self._adapters: Dict[Exchange, BaseExchangeAdapter] = {}
        self._orders: Dict[str, Order] = {}
        self._positions: Dict[str, Position] = {}

    def register_exchange(self, adapter: BaseExchangeAdapter):
        """注册交易所"""
        self._adapters[adapter.exchange] = adapter
        logger.info(f"Registered exchange: {adapter.exchange.value}")

    async def connect_all(self) -> Dict[Exchange, bool]:
        """连接所有交易所"""
        results = {}
        for exchange, adapter in self._adapters.items():
            results[exchange] = await adapter.connect()
        return results

    async def disconnect_all(self) -> None:
        """断开所有连接"""
        for adapter in self._adapters.values():
            await adapter.disconnect()

    async def execute_order(self, request: OrderRequest) -> OrderResult:
        """执行订单"""
        exchange = request.exchange

        if exchange not in self._adapters:
            return OrderResult(success=False, error=f"Exchange {exchange.value} not registered")

        adapter = self._adapters[exchange]
        result = await adapter.create_order(request)

        if result.success and result.order:
            self._orders[result.order.order_id] = result.order

        return result

    async def cancel_order(self, order_id: str, exchange: Exchange, symbol: str) -> bool:
        """取消订单"""
        if exchange in self._adapters:
            return await self._adapters[exchange].cancel_order(order_id, symbol)
        return False

    async def get_order(self, order_id: str, exchange: Exchange, symbol: str) -> Optional[Order]:
        """查询订单"""
        if exchange in self._adapters:
            return await self._adapters[exchange].get_order(order_id, symbol)
        return None

    async def get_all_positions(self) -> List[Position]:
        """获取所有持仓"""
        all_positions = []
        for adapter in self._adapters.values():
            positions = await adapter.get_positions()
            all_positions.extend(positions)

        # 更新到全局持仓
        for pos in all_positions:
            key = f"{pos.exchange.value}:{pos.symbol}"
            self._positions[key] = pos

        return all_positions

    async def get_balance(self, exchange: Exchange) -> Dict[str, float]:
        """获取余额"""
        if exchange in self._adapters:
            return await self._adapters[exchange].get_balance()
        return {}

    def get_order_history(self) -> List[Order]:
        """获取订单历史"""
        return list(self._orders.values())


# 全局实例
_execution_service: Optional[ExecutionService] = None


def get_execution_service() -> ExecutionService:
    """获取执行服务单例"""
    global _execution_service
    if _execution_service is None:
        _execution_service = ExecutionService()
    return _execution_service


async def init_execution_service() -> ExecutionService:
    """初始化执行服务"""
    service = get_execution_service()

    # 注册 Binance
    import os
    binance = BinanceAdapter(
        api_key=os.getenv("BINANCE_API_KEY"),
        api_secret=os.getenv("BINANCE_API_SECRET"),
        testnet=os.getenv("BINANCE_TESTNET", "true").lower() == "true"
    )
    service.register_exchange(binance)

    # 连接
    await service.connect_all()

    return service
