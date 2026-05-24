import os
import asyncio
import hmac
import hashlib
import time
import json
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
import aiohttp
from urllib.parse import urlencode

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
from infrastructure.config.defaults.infrastructure.external_apis import EXCHANGE_REST_APIS, EXCHANGE_WS_APIS

logger = get_logger("execution_service.adapters.binance_futures")


class BinanceFuturesAdapter(BaseExchangeAdapter):

    def __init__(
        self,
        api_key: str = None,
        api_secret: str = None,
        testnet: bool = True,
        timeout: int = 30,
    ):
        super().__init__(Exchange.BINANCE)
        self.api_key = api_key or os.getenv("BINANCE_API_KEY", "")
        self.api_secret = api_secret or os.getenv("BINANCE_API_SECRET", "")
        self.testnet = testnet
        self.timeout = timeout

        if self.testnet:
            self.BASE_URL = EXCHANGE_REST_APIS["binance"]["testnet_futures"]
            self.WS_URL = EXCHANGE_WS_APIS["binance"]["testnet_futures"]
        else:
            self.BASE_URL = EXCHANGE_REST_APIS["binance"]["futures"]
            self.WS_URL = EXCHANGE_WS_APIS["binance"]["futures"]

        self._session: Optional[aiohttp.ClientSession] = None
        self._orders: Dict[str, Order] = {}
        self._positions: Dict[str, Position] = {}
        self._leverage_cache: Dict[str, int] = {}

        self._ws_connection = None
        self._ws_listen_key = None
        self._ws_keepalive_task = None
        self._fill_callbacks: List[Callable] = []

    async def connect(self) -> bool:
        if not self.api_key or not self.api_secret:
            logger.warning("Binance Futures API credentials not provided")
            self._connected = True
            return True

        try:
            self._session = aiohttp.ClientSession()
            await self._start_user_data_stream()
            self._connected = True
            logger.info(f"Binance Futures adapter connected (testnet={self.testnet})")
            return True
        except Exception as e:
            logger.error(f"Failed to connect Binance Futures: {e}")
            return False

    async def disconnect(self) -> None:
        if self._ws_keepalive_task:
            self._ws_keepalive_task.cancel()
            try:
                await self._ws_keepalive_task
            except asyncio.CancelledError:
                pass

        if self._ws_connection:
            await self._ws_connection.close()

        if self._session:
            await self._session.close()

        self._connected = False
        logger.info("Binance Futures adapter disconnected")

    def _sign(self, params: Dict[str, Any]) -> str:
        query_string = urlencode(sorted(params.items()))
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return signature

    async def _request(self, method: str, endpoint: str, params: Dict = None) -> Dict:
        if not self._session:
            raise RuntimeError("Session not initialized")

        url = f"{self.BASE_URL}{endpoint}"
        headers = {"X-MBX-APIKEY": self.api_key}

        if params is None:
            params = {}

        params["timestamp"] = int(time.time() * 1000)
        params["signature"] = self._sign(params)

        try:
            timeout_config = aiohttp.ClientTimeout(total=self.timeout)

            async with self._session.request(
                method, url, params=params, headers=headers, timeout=timeout_config
            ) as response:
                data = await response.json()
                if response.status != 200:
                    logger.error(f"API error: {data}")
                    raise Exception(data.get("msg", "Unknown error"))
                return data
        except asyncio.TimeoutError:
            logger.error(f"Request timeout after {self.timeout}s: {endpoint}")
            raise
        except aiohttp.ClientError as e:
            logger.error(f"Request failed: {e}")
            raise

    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        try:
            await self._request(
                "POST",
                "/fapi/v1/leverage",
                {"symbol": symbol.upper(), "leverage": leverage}
            )
            self._leverage_cache[symbol.upper()] = leverage
            logger.info(f"Set leverage for {symbol}: {leverage}x")
            return True
        except Exception as e:
            logger.error(f"Failed to set leverage: {e}")
            return False

    async def _start_user_data_stream(self) -> None:
        try:
            data = await self._request("POST", "/fapi/v1/listenKey")
            self._ws_listen_key = data["listenKey"]

            self._ws_connection = await self._session.ws_connect(
                f"{self.WS_URL}/{self._ws_listen_key}"
            )

            self._ws_keepalive_task = asyncio.create_task(self._keepalive_listen_key())
            asyncio.create_task(self._ws_message_handler())

            logger.info("User Data Stream started")
        except Exception as e:
            logger.error(f"Failed to start user data stream: {e}")

    async def _keepalive_listen_key(self) -> None:
        while True:
            await asyncio.sleep(60 * 30)
            try:
                await self._request("PUT", "/fapi/v1/listenKey")
            except Exception as e:
                logger.error(f"Listen key keepalive failed: {e}")

    async def _ws_message_handler(self) -> None:
        async for msg in self._ws_connection:
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                await self._handle_ws_event(data)
            elif msg.type == aiohttp.WSMsgType.ERROR:
                logger.error(f"WebSocket error: {msg.data}")
                break

    async def _handle_ws_event(self, data: Dict) -> None:
        event_type = data.get("e")

        if event_type == "ORDER_TRADE_UPDATE":
            order_data = data["o"]
            await self._handle_order_update(order_data)

        elif event_type == "ACCOUNT_UPDATE":
            await self._handle_account_update(data["a"])

    async def _handle_order_update(self, order_data: Dict) -> None:
        order_id = order_data["c"]
        status_str = order_data["X"]
        filled_qty = float(order_data["l"])
        avg_price = float(order_data["L"]) if order_data["L"] else 0

        status_map = {
            "NEW": OrderStatus.SUBMITTED,
            "PARTIALLY_FILLED": OrderStatus.PARTIALLY_FILLED,
            "FILLED": OrderStatus.FILLED,
            "CANCELED": OrderStatus.CANCELLED,
            "REJECTED": OrderStatus.REJECTED,
        }

        new_status = status_map.get(status_str, OrderStatus.PENDING)

        if order_id in self._orders:
            order = self._orders[order_id]
            old_status = order.status
            order.status = new_status
            order.filled_quantity = float(order_data["q"])
            order.average_price = avg_price
            order.updated_at = datetime.now()

            if new_status == OrderStatus.FILLED:
                self._update_position(order)

            for callback in self._fill_callbacks:
                try:
                    await callback(order, old_status, new_status)
                except Exception as e:
                    logger.error(f"Fill callback error: {e}")

            logger.info(f"Order {order_id} updated: {old_status.value} -> {new_status.value}")

    async def _handle_account_update(self, account_data: Dict) -> None:
        positions_data = account_data.get("P", [])

        for pos_data in positions_data:
            symbol = pos_data["s"]
            qty = float(pos_data["pa"])
            entry_price = float(pos_data["ep"])
            unrealized_pnl = float(pos_data["up"])

            if abs(qty) > 0.0001:
                self._positions[symbol] = Position(
                    symbol=symbol,
                    exchange=self.exchange,
                    quantity=qty,
                    average_price=entry_price,
                    unrealized_pnl=unrealized_pnl,
                    market_type=MarketType.USDT_FUTURES,
                    leverage=self._leverage_cache.get(symbol, 1),
                    updated_at=datetime.now(),
                )
            elif symbol in self._positions:
                del self._positions[symbol]

    def on_fill(self, callback: Callable) -> None:
        self._fill_callbacks.append(callback)

    async def create_order(self, request: OrderRequest) -> OrderResult:
        if not self._connected:
            return OrderResult(success=False, error="Not connected")

        try:
            symbol = request.symbol.upper().replace("/", "")

            if request.leverage > 1 and symbol not in self._leverage_cache:
                await self.set_leverage(symbol, request.leverage)

            params = {
                "symbol": symbol,
                "side": request.side.value.upper(),
                "type": request.order_type.value.upper(),
                "quantity": request.quantity,
            }

            if request.order_type == OrderType.LIMIT:
                params["price"] = request.price
                params["timeInForce"] = request.time_in_force.value

            if request.order_type in [OrderType.STOP_MARKET, OrderType.STOP_LIMIT]:
                params["stopPrice"] = request.stop_price

            if request.reduce_only:
                params["reduceOnly"] = True

            if request.client_order_id:
                params["newClientOrderId"] = request.client_order_id

            result = await self._request("POST", "/fapi/v1/order", params)

            order = Order(
                order_id=result["clientOrderId"],
                symbol=request.symbol,
                exchange=self.exchange,
                side=request.side,
                order_type=request.order_type,
                quantity=float(result["origQty"]),
                price=request.price,
                status=OrderStatus.SUBMITTED,
                market_type=MarketType.USDT_FUTURES,
                client_order_id=result["clientOrderId"],
                exchange_order_id=result["orderId"],
                metadata={"reduce_only": request.reduce_only, "leverage": request.leverage},
            )

            self._orders[order.order_id] = order
            logger.info(f"Order created: {order.order_id}")

            return OrderResult(success=True, order=order)

        except Exception as e:
            logger.error(f"Failed to create order: {e}")
            return OrderResult(success=False, error=str(e))

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        try:
            symbol = symbol.upper().replace("/", "")
            await self._request(
                "DELETE",
                "/fapi/v1/order",
                {"symbol": symbol, "origClientOrderId": order_id}
            )

            if order_id in self._orders:
                self._orders[order_id].status = OrderStatus.CANCELLED
                self._orders[order_id].updated_at = datetime.now()

            logger.info(f"Order cancelled: {order_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to cancel order: {e}")
            return False

    async def get_order(self, order_id: str, symbol: str) -> Optional[Order]:
        try:
            symbol = symbol.upper().replace("/", "")
            result = await self._request(
                "GET",
                "/fapi/v1/order",
                {"symbol": symbol, "origClientOrderId": order_id}
            )

            status_map = {
                "NEW": OrderStatus.SUBMITTED,
                "PARTIALLY_FILLED": OrderStatus.PARTIALLY_FILLED,
                "FILLED": OrderStatus.FILLED,
                "CANCELED": OrderStatus.CANCELLED,
            }

            order = Order(
                order_id=result["clientOrderId"],
                symbol=result["symbol"],
                exchange=self.exchange,
                side=OrderSide(result["side"].lower()),
                order_type=OrderType(result["type"].lower()),
                quantity=float(result["origQty"]),
                price=float(result["price"]) if result.get("price") else None,
                status=status_map.get(result["status"], OrderStatus.PENDING),
                filled_quantity=float(result["executedQty"]),
                average_price=float(result["avgPrice"]) if result.get("avgPrice") else None,
                market_type=MarketType.USDT_FUTURES,
            )

            self._orders[order.order_id] = order
            return order

        except Exception as e:
            logger.error(f"Failed to get order: {e}")
            return self._orders.get(order_id)

    async def get_positions(self) -> List[Position]:
        try:
            result = await self._request("GET", "/fapi/v2/positionRisk")

            positions = []
            for pos in result:
                if float(pos["positionAmt"]) != 0:
                    position = Position(
                        symbol=pos["symbol"],
                        exchange=self.exchange,
                        quantity=float(pos["positionAmt"]),
                        average_price=float(pos["entryPrice"]),
                        current_price=float(pos["markPrice"]),
                        unrealized_pnl=float(pos["unRealizedProfit"]),
                        market_type=MarketType.USDT_FUTURES,
                        leverage=int(pos["leverage"]),
                        liquidation_price=float(pos["liquidationPrice"]),
                        updated_at=datetime.now(),
                    )
                    positions.append(position)
                    self._positions[pos["symbol"]] = position

            return positions

        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return [p for p in self._positions.values() if abs(p.quantity) > 0.0001]

    async def get_balance(self) -> Dict[str, float]:
        try:
            result = await self._request("GET", "/fapi/v2/balance")
            return {
                asset["asset"]: float(asset["availableBalance"])
                for asset in result
                if float(asset["availableBalance"]) > 0 or float(asset["marginBalance"]) > 0
            }
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return {}

    async def get_market_price(self, symbol: str) -> Optional[float]:
        try:
            symbol = symbol.upper().replace("/", "")
            async with self._session.get(
                f"{self.BASE_URL}/fapi/v1/ticker/price",
                params={"symbol": symbol}
            ) as resp:
                data = await resp.json()
                return float(data["price"])
        except Exception as e:
            logger.error(f"Failed to get market price: {e}")
            return None

    def _update_position(self, order: Order):
        symbol = order.symbol.upper().replace("/", "")

        if symbol not in self._positions:
            self._positions[symbol] = Position(
                symbol=symbol,
                exchange=self.exchange,
                quantity=0,
                average_price=0,
                market_type=MarketType.USDT_FUTURES,
            )

        pos = self._positions[symbol]
        multiplier = 1 if order.side == OrderSide.BUY else -1
        new_qty = pos.quantity + order.filled_quantity * multiplier

        if abs(new_qty) > 0.0001:
            if new_qty * pos.quantity >= 0:
                total_cost = pos.quantity * pos.average_price + order.filled_quantity * order.average_price * multiplier
                pos.quantity = new_qty
                pos.average_price = total_cost / pos.quantity
            else:
                pos.average_price = order.average_price
                pos.quantity = new_qty
        else:
            pos.quantity = 0
            pos.average_price = 0

        pos.updated_at = datetime.now()
