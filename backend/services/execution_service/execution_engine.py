"""
Execution Service - 订单执行服务

功能：
- 交易所 API 对接（Binance/OKX）
- 订单管理（创建、查询、取消）
- 持仓管理
- 交易历史
- 幂等性保护

架构：
Signal → ExecutionService → Exchange API → Order
"""

from enum import Enum
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from datetime import datetime
import asyncio

from infrastructure.logging import get_logger
from infrastructure.logging.sensitive_filter import safe_log, mask_sensitive_value
from shared.contracts import Exchange as SharedExchange
from shared.idempotency import (
    IdempotencyManager,
    get_idempotency_manager,
    ExecutionStatus,
)

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


@dataclass
class Order:
    """订单"""
    order_id: str
    symbol: str
    exchange: str
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
    idempotency_key: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "quantity": self.quantity,
            "price": self.price,
            "status": self.status.value,
            "filled_quantity": self.filled_quantity,
            "average_price": self.average_price,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "error": self.error,
            "idempotency_key": self.idempotency_key,
            "metadata": self.metadata,
        }


@dataclass
class Position:
    """持仓"""
    symbol: str
    exchange: str
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
    exchange: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    client_order_id: Optional[str] = None
    idempotency_key: Optional[str] = None


@dataclass
class OrderResult:
    """订单结果"""
    success: bool
    order: Optional[Order] = None
    error: Optional[str] = None
    duplicate: bool = False


class BaseExchangeAdapter:
    """交易所适配器基类"""

    def __init__(self, exchange: str):
        self.exchange = exchange

    async def connect(self) -> bool:
        raise NotImplementedError

    async def disconnect(self) -> None:
        raise NotImplementedError

    async def create_order(self, request: OrderRequest) -> OrderResult:
        raise NotImplementedError

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        raise NotImplementedError

    async def get_order(self, order_id: str, symbol: str) -> Optional[Order]:
        raise NotImplementedError

    async def get_positions(self) -> List[Position]:
        raise NotImplementedError

    async def get_balance(self) -> Dict[str, float]:
        raise NotImplementedError


class BinanceAdapter(BaseExchangeAdapter):
    """Binance 交易所适配器"""

    def __init__(self, api_key: str = None, api_secret: str = None, testnet: bool = True):
        super().__init__("binance")
        self.api_key = api_key
        self._api_secret = api_secret  # 使用下划线前缀标记为内部使用
        self.testnet = testnet
        self._connected = False
        self._orders: Dict[str, Order] = {}
        self._positions: Dict[str, Position] = {}

    async def connect(self) -> bool:
        if not self.api_key or not self._api_secret:
            logger.warning("Binance API credentials not provided, using mock mode")
            self._connected = True
            return True

        try:
            logger.info("Binance adapter connected (mock)")
            self._connected = True
            return True
        except Exception as e:
            logger.error(f"Failed to connect Binance: {e}")
            return False

    async def disconnect(self) -> None:
        self._connected = False
        logger.info("Binance adapter disconnected")

    async def create_order(self, request: OrderRequest) -> OrderResult:
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
                idempotency_key=request.idempotency_key,
                metadata={"client_order_id": request.client_order_id}
            )

            self._orders[order_id] = order

            if request.order_type == OrderType.MARKET:
                order.status = OrderStatus.FILLED
                order.filled_quantity = order.quantity
                order.average_price = request.price or 50000.0
                self._update_position(order)

            logger.info(f"Order created: {order_id} {request.side} {request.quantity} {request.symbol}")
            return OrderResult(success=True, order=order)

        except Exception as e:
            logger.error(f"Failed to create order: {e}")
            return OrderResult(success=False, error=str(e))

    def _update_position(self, order: Order):
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

        if pos.quantity < 0.001:
            pos.quantity = 0
            pos.average_price = 0

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        if order_id in self._orders:
            order = self._orders[order_id]
            if order.status in [OrderStatus.PENDING, OrderStatus.SUBMITTED]:
                order.status = OrderStatus.CANCELLED
                logger.info(f"Order cancelled: {order_id}")
                return True
        return False

    async def get_order(self, order_id: str, symbol: str) -> Optional[Order]:
        return self._orders.get(order_id)

    async def get_positions(self) -> List[Position]:
        return [p for p in self._positions.values() if p.quantity > 0]

    async def get_balance(self) -> Dict[str, float]:
        return {
            "USDT": 10000.0,
            "BTC": 0.5,
            "ETH": 5.0,
        }


class ExecutionService:
    """执行服务

    统一管理所有交易所的订单执行，支持幂等性保护
    """

    def __init__(self):
        self._adapters: Dict[str, BaseExchangeAdapter] = {}
        self._orders: Dict[str, Order] = {}
        self._positions: Dict[str, Position] = {}
        self._idempotency: Optional[IdempotencyManager] = None

    async def initialize(self):
        """初始化"""
        self._idempotency = await get_idempotency_manager()
        logger.info("ExecutionService initialized with idempotency protection")

    def register_exchange(self, adapter: BaseExchangeAdapter):
        self._adapters[adapter.exchange] = adapter
        logger.info(f"Registered exchange: {adapter.exchange}")

    async def connect_all(self) -> Dict[str, bool]:
        results = {}
        for exchange, adapter in self._adapters.items():
            results[exchange] = await adapter.connect()
        return results

    async def disconnect_all(self) -> None:
        for adapter in self._adapters.values():
            await adapter.disconnect()

    def _generate_idempotency_key(self, request: OrderRequest) -> str:
        """生成幂等性键"""
        if request.idempotency_key:
            return request.idempotency_key
        
        import hashlib
        key_parts = [
            request.exchange,
            request.symbol,
            request.side.value,
            request.order_type.value,
            str(request.quantity),
            str(request.price or ""),
            str(int(datetime.now().timestamp() * 1000) // 60000),
        ]
        key_str = ":".join(key_parts)
        return hashlib.sha256(key_str.encode()).hexdigest()[:16]

    async def execute_order(self, request: OrderRequest) -> OrderResult:
        """执行订单（带幂等性保护）"""
        exchange = request.exchange

        if exchange not in self._adapters:
            return OrderResult(success=False, error=f"Exchange {exchange} not registered")

        idempotency_key = self._generate_idempotency_key(request)
        
        can_execute, existing = await self._idempotency.check_and_lock(
            operation_type="order",
            operation_key=idempotency_key,
            request_data={
                "exchange": exchange,
                "symbol": request.symbol,
                "side": request.side.value,
                "type": request.order_type.value,
                "quantity": request.quantity,
                "price": request.price,
            },
        )

        if not can_execute:
            logger.info(f"Duplicate order detected: {idempotency_key}")
            
            if existing and existing.status == ExecutionStatus.COMPLETED:
                return OrderResult(
                    success=True,
                    order=Order(
                        order_id=existing.result.get("order_id", "unknown"),
                        symbol=request.symbol,
                        exchange=exchange,
                        side=request.side,
                        order_type=request.order_type,
                        quantity=request.quantity,
                        status=OrderStatus.FILLED,
                        idempotency_key=idempotency_key,
                    ),
                    duplicate=True,
                )
            
            return OrderResult(
                success=False,
                error="Order already processing",
                duplicate=True,
            )

        try:
            adapter = self._adapters[exchange]
            request.idempotency_key = idempotency_key
            result = await adapter.create_order(request)

            if result.success and result.order:
                self._orders[result.order.order_id] = result.order
                
                await self._idempotency.complete(
                    operation_type="order",
                    operation_key=idempotency_key,
                    result={
                        "order_id": result.order.order_id,
                        "status": result.order.status.value,
                        "filled_quantity": result.order.filled_quantity,
                        "average_price": result.order.average_price,
                    },
                )
            else:
                await self._idempotency.fail(
                    operation_type="order",
                    operation_key=idempotency_key,
                    error=result.error or "Unknown error",
                )

            return result

        except Exception as e:
            logger.error(f"Order execution failed: {e}")
            
            await self._idempotency.fail(
                operation_type="order",
                operation_key=idempotency_key,
                error=str(e),
            )
            
            return OrderResult(success=False, error=str(e))

    async def cancel_order(self, order_id: str, exchange: str, symbol: str) -> bool:
        if exchange in self._adapters:
            return await self._adapters[exchange].cancel_order(order_id, symbol)
        return False

    async def get_order(self, order_id: str, exchange: str, symbol: str) -> Optional[Order]:
        if exchange in self._adapters:
            return await self._adapters[exchange].get_order(order_id, symbol)
        return None

    async def get_all_positions(self) -> List[Position]:
        all_positions = []
        for adapter in self._adapters.values():
            positions = await adapter.get_positions()
            all_positions.extend(positions)

        for pos in all_positions:
            key = f"{pos.exchange}:{pos.symbol}"
            self._positions[key] = pos

        return all_positions

    async def get_balance(self, exchange: str) -> Dict[str, float]:
        if exchange in self._adapters:
            return await self._adapters[exchange].get_balance()
        return {}

    def get_order_history(self) -> List[Order]:
        return list(self._orders.values())

    async def get_execution_status(self, idempotency_key: str) -> Optional[ExecutionStatus]:
        """获取执行状态"""
        return await self._idempotency.get_status("order", idempotency_key)


_execution_service: Optional[ExecutionService] = None


async def get_execution_service() -> ExecutionService:
    """获取执行服务单例"""
    global _execution_service
    if _execution_service is None:
        _execution_service = ExecutionService()
        await _execution_service.initialize()
    return _execution_service


async def init_execution_service() -> ExecutionService:
    """初始化执行服务"""
    service = await get_execution_service()

    import os
    binance = BinanceAdapter(
        api_key=os.getenv("BINANCE_API_KEY"),
        api_secret=os.getenv("BINANCE_API_SECRET"),
        testnet=os.getenv("BINANCE_TESTNET", "true").lower() == "true"
    )
    
    # 安全地记录 Binance 配置（不显示密钥）
    has_api_key = bool(os.getenv("BINANCE_API_KEY"))
    has_api_secret = bool(os.getenv("BINANCE_API_SECRET"))
    logger.info(
        f"Binance adapter initialized - has_api_key={has_api_key}, has_api_secret={has_api_secret}, testnet={binance.testnet}"
    )
    
    service.register_exchange(binance)

    await service.connect_all()

    return service
