"""
Trading Service - 完整交易服务
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
import asyncio

from infrastructure.cache.redis_client import RedisClient, init_redis
from infrastructure.logging import get_logger

logger = get_logger("trading_service")


class TradingService:
    """交易服务 - 完整版"""

    POSITIONS_KEY = "trading:positions"
    ORDERS_KEY = "trading:orders"
    STATUS_KEY = "trading:status"
    ACCOUNTS_KEY = "trading:accounts"

    def __init__(self):
        self._redis: Optional[RedisClient] = None

    async def ensure_connection(self):
        if self._redis is None or not self._redis.is_connected:
            self._redis = await init_redis()

    @property
    def redis(self) -> RedisClient:
        if self._redis is None:
            raise RuntimeError("Redis not connected")
        return self._redis

    async def _init_default_account(self):
        accounts = await self.redis.get_json(self.ACCOUNTS_KEY)
        if not accounts:
            accounts = {
                "binance_spot": {
                    "exchange": "binance",
                    "market_type": "spot",
                    "balance": 10000.0,
                    "available_balance": 10000.0,
                    "margin_balance": 0,
                    "unrealized_pnl": 0,
                    "positions_count": 0,
                },
                "binance_usdt_futures": {
                    "exchange": "binance",
                    "market_type": "usdt_futures",
                    "balance": 10000.0,
                    "available_balance": 10000.0,
                    "margin_balance": 0,
                    "unrealized_pnl": 0,
                    "positions_count": 0,
                },
                "okx_usdt_futures": {
                    "exchange": "okx",
                    "market_type": "usdt_futures",
                    "balance": 10000.0,
                    "available_balance": 10000.0,
                    "margin_balance": 0,
                    "unrealized_pnl": 0,
                    "positions_count": 0,
                },
            }
            await self.redis.set_json(self.ACCOUNTS_KEY, accounts)

    async def get_accounts(self) -> Dict:
        await self._init_default_account()
        return await self.redis.get_json(self.ACCOUNTS_KEY) or {}

    async def get_positions(self) -> List[Dict]:
        positions = await self.redis.get_json(self.POSITIONS_KEY) or []
        await self._update_positions_pnl(positions)
        return positions

    async def _update_positions_pnl(self, positions: List[Dict]):
        for pos in positions:
            if not pos.get("entry_price"):
                continue

            current_price = pos.get("current_price", pos.get("entry_price"))
            entry_price = pos["entry_price"]
            leverage = pos.get("leverage", 1)
            side = pos.get("side", "long")

            if side == "long":
                price_change_pct = (current_price - entry_price) / entry_price
            else:
                price_change_pct = (entry_price - current_price) / entry_price

            unrealized_pnl_pct = price_change_pct * leverage
            unrealized_pnl = unrealized_pnl_pct * pos["quantity"] * entry_price

            pos["unrealized_pnl"] = round(unrealized_pnl, 2)
            pos["unrealized_pnl_pct"] = round(unrealized_pnl_pct, 4)

            if pos.get("stop_loss_pct"):
                sl_price = entry_price * (1 - pos["stop_loss_pct"] / 100) if side == "long" else entry_price * (1 + pos["stop_loss_pct"] / 100)
                pos["stop_loss_price"] = round(sl_price, 2)

            if pos.get("take_profit_pct"):
                tp_price = entry_price * (1 + pos["take_profit_pct"] / 100) if side == "long" else entry_price * (1 - pos["take_profit_pct"] / 100)
                pos["take_profit_price"] = round(tp_price, 2)

        await self.redis.set_json(self.POSITIONS_KEY, positions)

    async def get_open_orders(self) -> List[Dict]:
        orders = await self.redis.get_json(self.ORDERS_KEY)
        return orders if orders else []

    async def place_order(self, order_data: Dict) -> Dict:
        from uuid import uuid4

        from runtime.execution.router import get_execution_router, safe_execute
        from domain.execution.models import OrderRequest, OrderSide, OrderType as DomainOrderType, MarketType, Exchange

        order_id = str(uuid4())[:12]
        symbol = order_data["symbol"]
        side = order_data["side"]
        quantity = order_data["quantity"]
        exchange = order_data.get("exchange", "binance")
        market_type = order_data.get("market_type", "spot")
        leverage = order_data.get("leverage", 1)
        position_size_pct = order_data.get("position_size_pct", 10)
        stop_loss_pct = order_data.get("stop_loss_pct")
        take_profit_pct = order_data.get("take_profit_pct")

        entry_price = order_data.get("price", 50000.0)

        order = {
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": entry_price,
            "order_type": order_data.get("order_type", "market"),
            "market_type": market_type,
            "exchange": exchange,
            "leverage": leverage,
            "position_size_pct": position_size_pct,
            "stop_loss_pct": stop_loss_pct,
            "take_profit_pct": take_profit_pct,
            "stop_loss": entry_price * (1 - stop_loss_pct / 100) if stop_loss_pct else None,
            "take_profit": entry_price * (1 + take_profit_pct / 100) if take_profit_pct else None,
            "filled_quantity": 0,
            "avg_fill_price": None,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
        }

        await self.redis.set_json(f"order:{order_id}", order)

        orders = await self.redis.get_json(self.ORDERS_KEY) or []
        orders.append(order)
        await self.redis.set_json(self.ORDERS_KEY, orders)

        try:
            domain_side = OrderSide.BUY if side == "buy" else OrderSide.SELL
            domain_order_type = DomainOrderType.MARKET if order_data.get("order_type", "market") == "market" else DomainOrderType.LIMIT
            domain_exchange = Exchange(exchange)
            domain_market_type = MarketType(market_type)

            request = OrderRequest(
                symbol=symbol,
                exchange=domain_exchange,
                side=domain_side,
                order_type=domain_order_type,
                quantity=quantity,
                price=entry_price if domain_order_type == DomainOrderType.LIMIT else None,
                client_order_id=order_id,
                market_type=domain_market_type,
                leverage=leverage,
            )

            result = await safe_execute(request)

            if result.success and result.order:
                filled_order = result.order
                order["status"] = filled_order.status.value
                order["filled_quantity"] = filled_order.filled_quantity
                order["avg_fill_price"] = filled_order.average_price
                order["updated_at"] = datetime.now().isoformat()
                await self.redis.set_json(f"order:{order_id}", order)

                if filled_order.status.value == "filled":
                    await self._store_position_from_order(order)

                logger.info(f"Order executed via ExecutionRouter: {order_id} {side} {symbol} {quantity} @ {entry_price} [{market_type}] {leverage}x")
            else:
                order["status"] = "rejected"
                order["updated_at"] = datetime.now().isoformat()
                if result.error:
                    order["error"] = result.error
                await self.redis.set_json(f"order:{order_id}", order)
                logger.warning(f"Order rejected by ExecutionRouter: {order_id} - {result.error}")

        except Exception as e:
            logger.warning(f"ExecutionRouter unavailable, using local fill: {e}")
            await self._local_fill(order_id)

        return order

    async def _local_fill(self, order_id: str):
        order = await self.redis.get_json(f"order:{order_id}")
        if not order:
            return

        order["status"] = "filled"
        order["filled_quantity"] = order["quantity"]
        order["avg_fill_price"] = order["price"]
        order["updated_at"] = datetime.now().isoformat()
        await self.redis.set_json(f"order:{order_id}", order)

        await self._store_position_from_order(order)

        logger.info(f"Order filled locally (fallback): {order_id}")

    async def _store_position_from_order(self, order: Dict):
        positions = await self.redis.get_json(self.POSITIONS_KEY) or []
        position = {
            "position_id": str(order["order_id"]) + "_pos",
            "symbol": order["symbol"],
            "side": "long" if order["side"] == "buy" else "short",
            "quantity": order["quantity"],
            "entry_price": order["price"],
            "current_price": order["price"],
            "unrealized_pnl": 0,
            "unrealized_pnl_pct": 0,
            "realized_pnl": 0,
            "leverage": order["leverage"],
            "margin": order["quantity"] * order["price"] / order["leverage"],
            "market_type": order["market_type"],
            "exchange": order["exchange"],
            "stop_loss_pct": order.get("stop_loss_pct"),
            "take_profit_pct": order.get("take_profit_pct"),
            "stop_loss_price": order.get("stop_loss"),
            "take_profit_price": order.get("take_profit"),
            "opened_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        positions.append(position)
        await self.redis.set_json(self.POSITIONS_KEY, positions)

    # TODO: close_position should eventually go through execution_runtime
    async def close_position(self, close_data: Dict) -> Dict:
        symbol = close_data["symbol"]
        quantity = close_data.get("quantity")
        order_type = close_data.get("order_type", "market")

        positions = await self.redis.get_json(self.POSITIONS_KEY) or []

        for i, pos in enumerate(positions):
            if pos["symbol"] == symbol:
                close_qty = quantity if quantity else pos["quantity"]

                if close_qty < pos["quantity"]:
                    original_qty = pos["quantity"]
                    pos["quantity"] -= close_qty
                    pos["margin"] = pos["margin"] * (pos["quantity"] / original_qty)

                    closed_margin = pos["margin"] * (close_qty / original_qty)
                    realized_pnl = self._calculate_realized_pnl(pos, close_qty, close_qty == original_qty)

                    await self._refund_margin(pos["exchange"], pos["market_type"], closed_margin, realized_pnl)

                    positions[i] = pos
                    await self.redis.set_json(self.POSITIONS_KEY, positions)
                    logger.info(f"Position partially closed: {symbol} {close_qty}")
                    return {"success": True, "closed": close_qty, "remaining": pos["quantity"]}
                else:
                    realized_pnl = self._calculate_realized_pnl(pos, pos["quantity"], True)
                    closed_margin = pos["margin"]

                    positions.pop(i)
                    await self.redis.set_json(self.POSITIONS_KEY, positions)

                    await self._refund_margin(pos["exchange"], pos["market_type"], closed_margin, realized_pnl)

                    logger.info(f"Position fully closed: {symbol}")
                    return {"success": True, "closed": pos["quantity"], "remaining": 0, "realized_pnl": realized_pnl}

        raise ValueError(f"Position not found for {symbol}")

    def _calculate_realized_pnl(self, pos: Dict, close_qty: float, fully_closed: bool) -> float:
        entry_price = pos["entry_price"]
        current_price = pos.get("current_price", entry_price)
        leverage = pos.get("leverage", 1)
        side = pos.get("side", "long")

        if side == "long":
            pnl_pct = (current_price - entry_price) / entry_price
        else:
            pnl_pct = (entry_price - current_price) / entry_price

        realized_pnl_pct = pnl_pct * leverage
        realized_pnl = realized_pnl_pct * close_qty * entry_price

        return round(realized_pnl, 2)

    async def _refund_margin(self, exchange: str, market_type: str, margin: float, pnl: float):
        accounts = await self.redis.get_json(self.ACCOUNTS_KEY) or {}
        account_key = f"{exchange}_{market_type}"

        if account_key in accounts:
            accounts[account_key]["available_balance"] += margin + pnl
            accounts[account_key]["margin_balance"] -= margin
            accounts[account_key]["positions_count"] = max(0, accounts[account_key]["positions_count"] - 1)
            await self.redis.set_json(self.ACCOUNTS_KEY, accounts)

    # TODO: set_leverage should eventually go through execution_runtime
    async def set_leverage(self, data: Dict) -> Dict:
        symbol = data["symbol"]
        leverage = data["leverage"]

        positions = await self.redis.get_json(self.POSITIONS_KEY) or []

        for pos in positions:
            if pos["symbol"] == symbol:
                old_leverage = pos["leverage"]
                position_value = pos["quantity"] * pos["entry_price"]

                new_margin = position_value / leverage
                old_margin = pos["margin"]

                pos["leverage"] = leverage
                pos["margin"] = new_margin

                diff = old_margin - new_margin
                if diff > 0:
                    from infrastructure.runtime import get_runtime_governor
                    governor = get_runtime_governor()
                    governor.create_task(
                        self._refund_margin(pos["exchange"], pos["market_type"], diff, 0),
                        name=f"refund_margin_{symbol}",
                    )

                logger.info(f"Leverage updated: {symbol} {old_leverage}x -> {leverage}x")
                return {"success": True, "symbol": symbol, "leverage": leverage, "margin_change": -diff}

        raise ValueError(f"Position not found for {symbol}")

    # TODO: set_stop_loss_take_profit should eventually go through execution_runtime
    async def set_stop_loss_take_profit(self, data: Dict) -> Dict:
        symbol = data["symbol"]
        stop_loss_pct = data.get("stop_loss_pct")
        take_profit_pct = data.get("take_profit_pct")
        stop_loss_price = data.get("stop_loss_price")
        take_profit_price = data.get("take_profit_price")

        positions = await self.redis.get_json(self.POSITIONS_KEY) or []

        for pos in positions:
            if pos["symbol"] == symbol:
                entry_price = pos["entry_price"]
                side = pos.get("side", "long")

                pos["stop_loss_pct"] = stop_loss_pct
                pos["take_profit_pct"] = take_profit_pct

                if stop_loss_pct:
                    if side == "long":
                        pos["stop_loss_price"] = round(entry_price * (1 - stop_loss_pct / 100), 2)
                    else:
                        pos["stop_loss_price"] = round(entry_price * (1 + stop_loss_pct / 100), 2)
                else:
                    pos["stop_loss_price"] = stop_loss_price

                if take_profit_pct:
                    if side == "long":
                        pos["take_profit_price"] = round(entry_price * (1 + take_profit_pct / 100), 2)
                    else:
                        pos["take_profit_price"] = round(entry_price * (1 - take_profit_pct / 100), 2)
                else:
                    pos["take_profit_price"] = take_profit_price

                await self.redis.set_json(self.POSITIONS_KEY, positions)
                logger.info(f"SL/TP updated: {symbol} SL={pos['stop_loss_price']} TP={pos['take_profit_price']}")
                return {"success": True, "position": pos}

        raise ValueError(f"Position not found for {symbol}")

    # TODO: adjust_position should eventually go through execution_runtime
    async def adjust_position(self, data: Dict) -> Dict:
        symbol = data["symbol"]
        new_quantity = data["new_quantity"]
        new_leverage = data.get("new_leverage")

        positions = await self.redis.get_json(self.POSITIONS_KEY) or []

        for i, pos in enumerate(positions):
            if pos["symbol"] == symbol:
                old_quantity = pos["quantity"]
                entry_price = pos["entry_price"]

                if new_leverage:
                    pos["leverage"] = new_leverage

                pos["quantity"] = new_quantity
                pos["margin"] = new_quantity * entry_price / pos["leverage"]

                await self.redis.set_json(self.POSITIONS_KEY, positions)
                logger.info(f"Position adjusted: {symbol} {old_quantity} -> {new_quantity}")
                return {"success": True, "position": pos}

        raise ValueError(f"Position not found for {symbol}")

    async def check_stop_loss_take_profit(self):
        positions = await self.redis.get_json(self.POSITIONS_KEY) or []

        triggered = []
        for i, pos in enumerate(positions):
            current_price = pos.get("current_price", pos["entry_price"])
            side = pos.get("side", "long")

            should_close = False
            reason = ""

            if side == "long":
                if pos.get("stop_loss_price") and current_price <= pos["stop_loss_price"]:
                    should_close = True
                    reason = "stop_loss"
                elif pos.get("take_profit_price") and current_price >= pos["take_profit_price"]:
                    should_close = True
                    reason = "take_profit"
            else:
                if pos.get("stop_loss_price") and current_price >= pos["stop_loss_price"]:
                    should_close = True
                    reason = "stop_loss"
                elif pos.get("take_profit_price") and current_price <= pos["take_profit_price"]:
                    should_close = True
                    reason = "take_profit"

            if should_close:
                try:
                    result = await self.close_position({"symbol": pos["symbol"]})
                    triggered.append({"symbol": pos["symbol"], "reason": reason, **result})
                    logger.info(f"SL/TP triggered: {pos['symbol']} reason={reason}")
                except Exception as e:
                    logger.error(f"Failed to close position {pos['symbol']}: {e}")

        return triggered

    async def get_trading_status(self) -> Dict:
        positions = await self.get_positions()
        orders = await self.get_open_orders()
        accounts = await self.get_accounts()

        total_equity = sum(acc.get("balance", 0) + acc.get("unrealized_pnl", 0) for acc in accounts.values())
        total_unrealized_pnl = sum(p.get("unrealized_pnl", 0) for p in positions)
        total_realized_pnl = sum(acc.get("realized_pnl", 0) for acc in accounts.values())
        total_position_value = sum(p["quantity"] * p.get("current_price", p["entry_price"]) for p in positions)
        margin_balance = sum(acc.get("margin_balance", 0) for acc in accounts.values())
        available_balance = sum(acc.get("available_balance", 0) for acc in accounts.values())

        return {
            "mode": "hybrid",
            "auto_approve_threshold": 100.0,
            "total_equity": round(total_equity, 2),
            "total_unrealized_pnl": round(total_unrealized_pnl, 2),
            "total_realized_pnl": round(total_realized_pnl, 2),
            "daily_pnl": round(total_unrealized_pnl, 2),
            "total_position_value": round(total_position_value, 2),
            "margin_balance": round(margin_balance, 2),
            "available_balance": round(available_balance, 2),
            "positions_count": len(positions),
            "open_orders_count": len([o for o in orders if o.get("status") != "filled"]),
            "timestamp": datetime.now().isoformat(),
        }

    async def set_trading_mode(self, mode: str, threshold: float = None) -> Dict:
        status = await self.redis.get_json(self.STATUS_KEY) or {}
        status["mode"] = mode
        if threshold is not None:
            status["auto_approve_threshold"] = threshold
        status["updated_at"] = datetime.now().isoformat()
        await self.redis.set_json(self.STATUS_KEY, status)

        logger.info(f"Trading mode set to: {mode}")
        return status

    async def health_check(self) -> Dict:
        accounts = await self.get_accounts()
        return {
            "status": "healthy",
            "exchanges": {k.split("_")[0]: "connected" for k in accounts.keys()},
            "market_types": {k.split("_")[1] if "_" in k else "spot": "ready" for k in accounts.keys()},
            "timestamp": datetime.now().isoformat(),
        }


_trading_service: Optional[TradingService] = None


def get_trading_service() -> TradingService:
    global _trading_service
    if _trading_service is None:
        _trading_service = TradingService()
    return _trading_service
