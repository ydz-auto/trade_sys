import os
from typing import Dict, List, Optional
from datetime import datetime

from domain.execution.models import (
    Order,
    OrderRequest,
    OrderResult,
    Position,
    Exchange,
    OrderSide,
    OrderType,
    OrderStatus,
    MarketType,
)
from engines.adapters.exchange.base_adapter import BaseExchangeAdapter
from infrastructure.logging import get_logger

logger = get_logger("execution_service.adapters.binance")


class BinanceAdapter(BaseExchangeAdapter):

    def __init__(
        self,
        api_key: str = None,
        api_secret: str = None,
        testnet: bool = True,
        market_type: MarketType = MarketType.SPOT,
    ):
        super().__init__(Exchange.BINANCE)
        self.api_key = api_key or os.getenv("BINANCE_API_KEY")
        self.api_secret = api_secret or os.getenv("BINANCE_API_SECRET")
        self.testnet = testnet
        self.market_type = market_type

        self._exchange = None
        self._orders: Dict[str, Order] = {}
        self._positions: Dict[str, Position] = {}

    async def connect(self) -> bool:
        if not self.api_key or not self.api_secret:
            logger.warning("Binance API credentials not provided, using mock mode")
            self._connected = True
            return True

        try:
            import ccxt.async_support as ccxt

            if self.market_type == MarketType.SPOT:
                self._exchange = ccxt.binance({
                    "apiKey": self.api_key,
                    "secret": self.api_secret,
                    "enableRateLimit": True,
                    "options": {"defaultType": "spot"},
                })
            elif self.market_type == MarketType.USDT_FUTURES:
                self._exchange = ccxt.binance({
                    "apiKey": self.api_key,
                    "secret": self.api_secret,
                    "enableRateLimit": True,
                    "options": {"defaultType": "future"},
                })
                if self.testnet:
                    self._exchange.set_sandbox_mode(True)

            logger.info(f"Binance adapter connected (market_type={self.market_type.value}, testnet={self.testnet})")
            self._connected = True
            return True

        except ImportError:
            logger.warning("ccxt not installed, using mock mode")
            self._connected = True
            return True
        except Exception as e:
            logger.error(f"Failed to connect Binance: {e}")
            return False

    async def disconnect(self) -> None:
        if self._exchange:
            await self._exchange.close()
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
                market_type=request.market_type,
                metadata={
                    "client_order_id": request.client_order_id,
                    "leverage": request.leverage,
                    "reduce_only": request.reduce_only,
                },
            )

            if self._exchange:
                params = {}
                if request.market_type == MarketType.USDT_FUTURES:
                    if request.reduce_only:
                        params["reduceOnly"] = True

                if request.order_type == OrderType.MARKET:
                    result = await self._exchange.create_market_order(
                        symbol=request.symbol,
                        side=request.side.value,
                        amount=request.quantity,
                        params=params,
                    )
                elif request.order_type == OrderType.LIMIT:
                    result = await self._exchange.create_limit_order(
                        symbol=request.symbol,
                        side=request.side.value,
                        amount=request.quantity,
                        price=request.price,
                        params=params,
                    )
                else:
                    result = await self._exchange.create_order(
                        symbol=request.symbol,
                        type=request.order_type.value,
                        side=request.side.value,
                        amount=request.quantity,
                        price=request.price,
                        params=params,
                    )

                order.exchange_order_id = result.get("id")
                order.status = OrderStatus.SUBMITTED
                order.updated_at = datetime.now()

                logger.info(f"Order created on Binance: {order.exchange_order_id}")
            else:
                if request.order_type == OrderType.MARKET:
                    order.status = OrderStatus.FILLED
                    order.filled_quantity = order.quantity
                    order.average_price = request.price or 50000.0
                    self._update_position(order)

            self._orders[order_id] = order
            logger.info(f"Order created: {order_id} {request.side.value} {request.quantity} {request.symbol}")

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
                average_price=0,
                market_type=order.market_type,
            )

        pos = self._positions[symbol]

        if order.side == OrderSide.BUY:
            total_cost = pos.quantity * pos.average_price + order.filled_quantity * order.average_price
            pos.quantity += order.filled_quantity
            pos.average_price = total_cost / pos.quantity if pos.quantity > 0 else 0
        else:
            pos.quantity -= order.filled_quantity

        if abs(pos.quantity) < 1e-8:
            pos.quantity = 0
            pos.average_price = 0

        pos.updated_at = datetime.now()

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        if order_id in self._orders:
            order = self._orders[order_id]
            if order.status in [OrderStatus.PENDING, OrderStatus.SUBMITTED]:
                if self._exchange:
                    try:
                        await self._exchange.cancel_order(order_id, symbol)
                    except Exception as e:
                        logger.error(f"Failed to cancel order on exchange: {e}")
                        return False

                order.status = OrderStatus.CANCELLED
                order.updated_at = datetime.now()
                logger.info(f"Order cancelled: {order_id}")
                return True
        return False

    async def get_order(self, order_id: str, symbol: str) -> Optional[Order]:
        if self._exchange:
            try:
                result = await self._exchange.fetch_order(order_id, symbol)
                if order_id in self._orders:
                    order = self._orders[order_id]
                    order.status = OrderStatus(result.get("status", "pending"))
                    order.filled_quantity = result.get("filled", 0.0)
                    order.average_price = result.get("average", 0.0)
                    order.updated_at = datetime.now()
                    return order
            except Exception as e:
                logger.error(f"Failed to fetch order: {e}")

        return self._orders.get(order_id)

    async def get_positions(self) -> List[Position]:
        if self._exchange and self.market_type == MarketType.USDT_FUTURES:
            try:
                positions = await self._exchange.fetch_positions()
                result = []
                for pos in positions:
                    if float(pos.get("contracts", 0)) != 0:
                        position = Position(
                            symbol=pos["symbol"],
                            exchange=self.exchange,
                            quantity=float(pos.get("contracts", 0)),
                            average_price=float(pos.get("entryPrice", 0)),
                            current_price=float(pos.get("markPrice", 0)),
                            unrealized_pnl=float(pos.get("unrealizedPnl", 0)),
                            market_type=self.market_type,
                            leverage=int(pos.get("leverage", 1)),
                            margin=float(pos.get("initialMargin", 0)),
                            liquidation_price=float(pos.get("liquidationPrice", 0)),
                        )
                        result.append(position)
                        self._positions[pos["symbol"]] = position
                return result
            except Exception as e:
                logger.error(f"Failed to fetch positions: {e}")

        return [p for p in self._positions.values() if abs(p.quantity) > 1e-8]

    async def get_balance(self) -> Dict[str, float]:
        if self._exchange:
            try:
                balance = await self._exchange.fetch_balance()
                return {
                    currency: float(data.get("free", 0))
                    for currency, data in balance.items()
                    if float(data.get("free", 0)) > 0 or float(data.get("used", 0)) > 0
                }
            except Exception as e:
                logger.error(f"Failed to fetch balance: {e}")

        return {
            "USDT": 10000.0,
            "BTC": 0.5,
            "ETH": 5.0,
        }

    async def get_market_price(self, symbol: str) -> Optional[float]:
        if self._exchange:
            try:
                ticker = await self._exchange.fetch_ticker(symbol)
                return ticker.get("last")
            except Exception as e:
                logger.error(f"Failed to fetch market price: {e}")

        return None

    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        if self.market_type != MarketType.USDT_FUTURES:
            logger.warning("set_leverage only available for futures")
            return False

        if self._exchange:
            try:
                await self._exchange.set_leverage(leverage, symbol)
                logger.info(f"Leverage set to {leverage}x for {symbol}")
                return True
            except Exception as e:
                logger.error(f"Failed to set leverage: {e}")
                return False

        return True
