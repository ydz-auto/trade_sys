"""
OKX Adapter

OKX 交易所适配器（现货 + 合约）
支持：
- 现货交易
- USDT 永续合约
- WebSocket 实时更新
- 杠杆设置
- 减少只有订单
"""

import os
import asyncio
import hmac
import hashlib
import base64
import json
import time
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime

import aiohttp

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
from services.execution_service.adapters.base import BaseExchangeAdapter
from infrastructure.logging import get_logger

logger = get_logger("execution_service.adapters.okx")


class OKXAdapter(BaseExchangeAdapter):
    """OKX 交易所适配器"""

    # API 基础 URL
    BASE_URL = "https://www.okx.com"
    WS_PUBLIC_URL = "wss://ws.okx.com:8443/ws/public"
    WS_PRIVATE_URL = "wss://ws.okx.com:8443/ws/private"

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        passphrase: Optional[str] = None,
        testnet: bool = True,
        market_type: MarketType = MarketType.SWAP,
    ):
        super().__init__(Exchange.OKX)

        self.api_key = api_key or os.getenv("OKX_API_KEY", "")
        self.api_secret = api_secret or os.getenv("OKX_API_SECRET", "")
        self.passphrase = passphrase or os.getenv("OKX_PASSPHRASE", "")
        self.testnet = testnet
        self.market_type = market_type

        # 测试网配置
        if self.testnet:
            self.BASE_URL = "https://www.okx.com"
            self.WS_PUBLIC_URL = "wss://wspap.okx.com:8443/ws/public"
            self.WS_PRIVATE_URL = "wss://wspap.okx.com:8443/ws/private"
            logger.info(f"Using OKX {'TESTNET' if testnet else 'MAINNET'}")

        self._session: Optional[aiohttp.ClientSession] = None
        self._orders: Dict[str, Order] = {}
        self._positions: Dict[str, Position] = {}
        self._leverage_cache: Dict[str, int] = {}

        self._ws_connection = None
        self._ws_keepalive_task = None
        self._fill_callbacks: List[Callable] = []

    def _sign(self, timestamp: str, method: str, request_path: str, body: str = "") -> str:
        """OKX API 签名"""
        message = timestamp + method.upper() + request_path + body
        mac = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        )
        return base64.b64encode(mac.digest()).decode()

    def _get_headers(self, method: str, request_path: str, body: str = "") -> Dict[str, str]:
        """获取签名头"""
        timestamp = str(int(time.time() * 1000) / 1000)
        signature = self._sign(timestamp, method, request_path, body)
        return {
            "OK-ACCESS-KEY": self.api_key,
            "OK-ACCESS-SIGN": signature,
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json",
        }

    async def connect(self) -> bool:
        """连接 OKX"""
        try:
            self._session = aiohttp.ClientSession()

            # 如果有 API Key，启动 WebSocket
            if self.api_key and self.api_secret:
                await self._start_user_data_stream()
                logger.info("OKX WebSocket connected")

            self._connected = True
            logger.info("OKX adapter connected")
            return True
        except Exception as e:
            logger.error(f"Failed to connect OKX: {e}")
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """断开连接"""
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
        logger.info("OKX adapter disconnected")

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        body: Optional[Dict] = None,
    ) -> Dict:
        """发送签名请求"""
        if not self._session:
            raise RuntimeError("Session not initialized")

        url = f"{self.BASE_URL}{endpoint}"
        request_path = endpoint
        request_body = json.dumps(body) if body else ""

        headers = self._get_headers(method, request_path, request_body)

        try:
            if method.upper() == "GET":
                async with self._session.get(url, params=params, headers=headers) as resp:
                    data = await resp.json()
            elif method.upper() == "POST":
                async with self._session.post(url, json=body, headers=headers) as resp:
                    data = await resp.json()
            elif method.upper() == "DELETE":
                async with self._session.delete(url, params=params, headers=headers) as resp:
                    data = await resp.json()
            else:
                raise ValueError(f"Unsupported method: {method}")

            if data.get("code") != "0":
                raise Exception(f"OKX API Error: {data.get('code')} - {data.get('msg')}")
            return data.get("data", [])

        except aiohttp.ClientError as e:
            logger.error(f"Request failed: {e}")
            raise

    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        """设置杠杆"""
        try:
            inst_id = self._to_okx_symbol(symbol)
            await self._request(
                "POST",
                "/api/v5/account/set-leverage",
                body={
                    "instId": inst_id,
                    "leverage": str(leverage),
                    "mgnMode": "cross",  # 全仓
                },
            )
            self._leverage_cache[inst_id] = leverage
            logger.info(f"Set leverage for {inst_id}: {leverage}x")
            return True
        except Exception as e:
            logger.error(f"Failed to set leverage: {e}")
            return False

    async def create_order(self, request: OrderRequest) -> OrderResult:
        """创建订单"""
        if not self._connected:
            return OrderResult(success=False, error="Not connected")

        try:
            inst_id = self._to_okx_symbol(request.symbol)

            # 如果是合约且需要设置杠杆
            if request.market_type in [MarketType.SWAP, MarketType.USDT_FUTURES] and request.leverage > 1:
                if inst_id not in self._leverage_cache:
                    await self.set_leverage(inst_id, request.leverage)

            # 构建订单参数
            side = request.side.value.upper()

            ord_type = {
                OrderType.MARKET: "market",
                OrderType.LIMIT: "limit",
                OrderType.STOP_MARKET: "conditional",
                OrderType.STOP_LIMIT: "conditional",
            }.get(request.order_type, "market")

            order_request = {
                "instId": inst_id,
                "tdMode": "cross",
                "clOrdId": f"ord_{int(time.time() * 1000)}",
                "side": side,
                "ordType": ord_type,
                "sz": str(request.quantity),
                "posSide": "net" if request.reduce_only else "",
            }

            if request.order_type == OrderType.LIMIT and request.price:
                order_request["px"] = str(request.price)

            if request.reduce_only:
                order_request["reduceOnly"] = True

            # 发送请求
            response = await self._request(
                "POST",
                "/api/v5/trade/order",
                body=order_request,
            )

            order_id = response[0]["ordId"] if response else None
            cl_ord_id = response[0]["clOrdId"] if response else None

            order = Order(
                order_id=cl_ord_id or f"okx_{int(time.time() * 1000)}",
                client_order_id=cl_ord_id,
                exchange_order_id=order_id,
                symbol=request.symbol,
                exchange=self.exchange,
                side=request.side,
                order_type=request.order_type,
                quantity=request.quantity,
                price=request.price,
                status=OrderStatus.SUBMITTED,
                market_type=request.market_type,
                leverage=request.leverage,
                reduce_only=request.reduce_only,
            )

            self._orders[order.order_id] = order
            logger.info(f"OKX order created: {order.order_id}")
            return OrderResult(success=True, order=order)

        except Exception as e:
            logger.error(f"Failed to create OKX order: {e}")
            return OrderResult(success=False, error=str(e))

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """取消订单"""
        try:
            inst_id = self._to_okx_symbol(symbol)
            await self._request(
                "POST",
                "/api/v5/trade/cancel-order",
                body={
                    "instId": inst_id,
                    "clOrdId": order_id,
                },
            )

            if order_id in self._orders:
                self._orders[order_id].status = OrderStatus.CANCELLED
                self._orders[order_id].updated_at = datetime.now()

            logger.info(f"OKX order cancelled: {order_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel OKX order: {e}")
            return False

    async def get_order(self, order_id: str, symbol: str) -> Optional[Order]:
        """查询订单"""
        try:
            inst_id = self._to_okx_symbol(symbol)
            response = await self._request(
                "GET",
                "/api/v5/trade/order",
                params={
                    "instId": inst_id,
                    "clOrdId": order_id,
                },
            )

            if not response:
                return None

            order_data = response[0]

            status_map = {
                "live": OrderStatus.SUBMITTED,
                "partially_filled": OrderStatus.PARTIALLY_FILLED,
                "filled": OrderStatus.FILLED,
                "canceled": OrderStatus.CANCELLED,
                "rejected": OrderStatus.REJECTED,
                "failed": OrderStatus.FAILED,
            }

            order = Order(
                order_id=order_data["clOrdId"],
                client_order_id=order_data["clOrdId"],
                exchange_order_id=order_data["ordId"],
                symbol=symbol,
                exchange=self.exchange,
                side=OrderSide(order_data["side"].lower()),
                order_type=OrderType(order_data["ordType"].lower()),
                quantity=float(order_data["sz"]),
                price=float(order_data.get("px", 0)),
                status=status_map.get(order_data["state"], OrderStatus.PENDING),
                filled_quantity=float(order_data.get("fillSz", 0)),
                avg_fill_price=float(order_data.get("avgPx", 0)),
                market_type=self.market_type,
            )

            self._orders[order.order_id] = order
            return order

        except Exception as e:
            logger.error(f"Failed to get OKX order: {e}")
            return self._orders.get(order_id)

    async def get_positions(self) -> List[Position]:
        """获取持仓"""
        try:
            response = await self._request("GET", "/api/v5/account/positions", params={"instType": "SWAP"})

            positions = []
            for pos_data in response:
                if abs(float(pos_data["pos"])) > 0:
                    position = Position(
                        symbol=pos_data["instId"].replace("-USDT-SWAP", "USDT"),
                        exchange=self.exchange,
                        quantity=float(pos_data["pos"]),
                        avg_entry_price=float(pos_data["avgPx"]),
                        current_price=float(pos_data["upl"]),
                        unrealized_pnl=float(pos_data["upl"]),
                        realized_pnl=float(pos_data.get("realizedPnl", 0)),
                        market_type=MarketType.SWAP,
                        leverage=int(pos_data.get("lever", 1)),
                        liquidation_price=float(pos_data.get("liqPx", 0)) if pos_data.get("liqPx") else None,
                    )
                    positions.append(position)
                    self._positions[position.symbol] = position

            return positions
        except Exception as e:
            logger.error(f"Failed to get OKX positions: {e}")
            return [p for p in self._positions.values() if abs(p.quantity) > 0.0001]

    async def get_balance(self) -> Dict[str, float]:
        """获取余额"""
        try:
            response = await self._request("GET", "/api/v5/account/balance")

            if not response:
                return {}

            balances = {}
            for detail in response[0].get("details", []):
                asset = detail["ccy"]
                available = float(detail.get("availEq", 0))
                if available > 0:
                    balances[asset] = available

            return balances
        except Exception as e:
            logger.error(f"Failed to get OKX balance: {e}")
            return {}

    async def get_market_price(self, symbol: str) -> Optional[float]:
        """获取市场价格"""
        try:
            inst_id = self._to_okx_symbol(symbol)
            response = await self._request("GET", "/api/v5/market/ticker", params={"instId": inst_id})
            if response:
                return float(response[0]["last"])
            return None
        except Exception as e:
            logger.error(f"Failed to get OKX market price: {e}")
            return None

    async def _start_user_data_stream(self) -> None:
        """启动 WebSocket 用户数据流"""
        try:
            self._ws_connection = await self._session.ws_connect(self.WS_PRIVATE_URL)

            # 登录认证
            timestamp = str(int(time.time() * 1000) / 1000)
            sign = self._sign(timestamp, "GET", "/users/self/verify")

            auth_request = {
                "op": "login",
                "args": [{
                    "apiKey": self.api_key,
                    "passphrase": self.passphrase,
                    "timestamp": timestamp,
                    "sign": sign,
                }]
            }

            await self._ws_connection.send_json(auth_request)

            # 订阅订单、账户更新
            await self._ws_connection.send_json({
                "op": "subscribe",
                "args": [
                    {"channel": "orders", "instType": "SWAP"},
                    {"channel": "account"},
                ],
            })

            self._ws_keepalive_task = asyncio.create_task(self._ws_message_handler())
            logger.info("OKX WebSocket stream started")

        except Exception as e:
            logger.error(f"Failed to start OKX WebSocket: {e}")

    async def _ws_message_handler(self) -> None:
        """WebSocket 消息处理"""
        try:
            async for msg in self._ws_connection:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    await self._handle_ws_event(data)
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f"OKX WebSocket error: {msg.data}")
                    break
        except Exception as e:
            logger.error(f"OKX WebSocket handler error: {e}")

    async def _handle_ws_event(self, data: Dict) -> None:
        """处理 WebSocket 事件"""
        if data.get("event") == "login":
            logger.info("OKX WebSocket logged in")
            return

        if data.get("event") == "subscribe":
            logger.info(f"OKX WebSocket subscribed: {data}")
            return

        arg = data.get("arg", {})
        channel = arg.get("channel")

        if channel == "orders":
            for order_data in data.get("data", []):
                await self._handle_ws_order_update(order_data)
        elif channel == "account":
            pass

    async def _handle_ws_order_update(self, order_data: Dict) -> None:
        """处理订单更新"""
        cl_ord_id = order_data.get("clOrdId")
        if not cl_ord_id:
            return

        status_map = {
            "live": OrderStatus.SUBMITTED,
            "partially_filled": OrderStatus.PARTIALLY_FILLED,
            "filled": OrderStatus.FILLED,
            "canceled": OrderStatus.CANCELLED,
            "rejected": OrderStatus.REJECTED,
        }

        status = status_map.get(order_data["state"], OrderStatus.PENDING)
        filled_qty = float(order_data.get("fillSz", 0))
        avg_px = float(order_data.get("avgPx", 0)) if order_data.get("avgPx") else 0

        if cl_ord_id in self._orders:
            order = self._orders[cl_ord_id]
            old_status = order.status
            order.status = status
            order.filled_quantity = filled_qty
            order.avg_fill_price = avg_px
            order.updated_at = datetime.now()

            for callback in self._fill_callbacks:
                try:
                    await callback(order, old_status, status)
                except Exception as e:
                    logger.error(f"OKX fill callback error: {e}")

            logger.info(f"OKX order updated: {cl_ord_id} - {old_status.value} -> {status.value}")

    def _to_okx_symbol(self, symbol: str) -> str:
        """转换符号到 OKX 格式"""
        symbol = symbol.upper()
        if "USDT" in symbol and "/" not in symbol:
            if symbol.endswith("USDT"):
                base = symbol[:-4]
                return f"{base}-USDT-SWAP"
        elif "/" in symbol:
            base, quote = symbol.split("/")
            return f"{base}-{quote}-SWAP" if self.market_type in [MarketType.SWAP, MarketType.USDT_FUTURES] else f"{base}-{quote}"
        return symbol

    def on_fill(self, callback: Callable) -> None:
        """注册成交回调"""
        self._fill_callbacks.append(callback)
