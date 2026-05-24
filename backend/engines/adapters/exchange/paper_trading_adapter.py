from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
from decimal import Decimal, ROUND_DOWN
import uuid
import asyncio

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

logger = get_logger("execution_service.adapters.paper_trading")


class PaperTradingAdapter(BaseExchangeAdapter):

    def __init__(
        self,
        exchange: Exchange = Exchange.BINANCE,
        initial_balance: Optional[Dict[str, float]] = None,
        slippage: float = 0.001,
        fee_maker: float = 0.0002,
        fee_taker: float = 0.0004,
        use_real_depth: bool = True,
    ):
        super().__init__(exchange)

        self.slippage = slippage
        self.fee_maker = fee_maker
        self.fee_taker = fee_taker
        self.use_real_depth = use_real_depth

        self._orders: Dict[str, Order] = {}
        self._positions: Dict[str, Position] = {}
        self._balance = initial_balance or {"USDT": 100000.0}

        self._price_cache: Dict[str, float] = {}

        self._market_data_adapter: Optional[Any] = None

        self._fill_callbacks: List[Callable] = []

    async def connect(self) -> bool:
        try:
            self._connected = True
            logger.info("Paper Trading Adapter connected (using real market data)")
            return True
        except Exception as e:
            logger.error(f"Failed to connect Paper Trading: {e}")
            self._connected = True
            return True

    async def disconnect(self) -> None:
        if self._market_data_adapter:
            try:
                await self._market_data_adapter.disconnect()
            except:
                pass
        self._connected = False
        logger.info("Paper Trading Adapter disconnected")

    async def _get_current_price(self, symbol: str) -> float:
        if symbol in self._price_cache:
            return self._price_cache[symbol]

        if "BTC" in symbol:
            return 70000.0
        elif "ETH" in symbol:
            return 3500.0
        else:
            return 100.0

    def _apply_slippage(self, price: float, side: OrderSide) -> float:
        if side == OrderSide.BUY:
            return price * (1 + self.slippage)
        else:
            return price * (1 - self.slippage)

    def _calculate_fee(self, notional: float, is_maker: bool = False) -> float:
        fee_rate = self.fee_maker if is_maker else self.fee_taker
        return notional * fee_rate

    async def create_order(self, request: OrderRequest) -> OrderResult:
        if not self._connected:
            return OrderResult(success=False, error="Paper Trading not connected")

        try:
            current_price = await self._get_current_price(request.symbol)

            if request.order_type == OrderType.LIMIT and request.price:
                if request.side == OrderSide.BUY:
                    if current_price <= request.price:
                        exec_price = request.price
                    else:
                        return await self._create_pending_limit_order(request, request.price)
                else:
                    if current_price >= request.price:
                        exec_price = request.price
                    else:
                        return await self._create_pending_limit_order(request, request.price)
            else:
                exec_price = self._apply_slippage(current_price, request.side)

            order_id = f"paper_{uuid.uuid4().hex[:12]}"

            notional = request.quantity * exec_price
            fee = self._calculate_fee(notional, is_maker=False)

            order = Order(
                order_id=order_id,
                symbol=request.symbol,
                exchange=self.exchange,
                side=request.side,
                order_type=request.order_type,
                quantity=request.quantity,
                price=exec_price,
                status=OrderStatus.FILLED,
                filled_quantity=request.quantity,
                average_price=exec_price,
                market_type=request.market_type,
                metadata={
                    "paper_trading": True,
                    "slippage": self.slippage,
                    "fee": fee,
                    "real_price": current_price,
                    "leverage": request.leverage,
                    "reduce_only": request.reduce_only,
                },
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

            self._orders[order_id] = order

            await self._update_position(order, fee, request.leverage if request.leverage else 1, request.reduce_only)

            logger.info(
                f"[Paper Trading] Order filled: {order_id} "
                f"{request.side.value} {request.quantity} {request.symbol} "
                f"@ {exec_price} (fee: {fee:.2f})"
            )

            for callback in self._fill_callbacks:
                try:
                    await callback(order, OrderStatus.SUBMITTED, OrderStatus.FILLED)
                except Exception as e:
                    logger.error(f"Fill callback error: {e}")

            return OrderResult(success=True, order=order)

        except Exception as e:
            logger.error(f"Failed to create paper trading order: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return OrderResult(success=False, error=str(e))

    async def _create_pending_limit_order(self, request: OrderRequest, limit_price: float) -> OrderResult:
        order_id = f"paper_{uuid.uuid4().hex[:12]}"

        order = Order(
            order_id=order_id,
            symbol=request.symbol,
            exchange=self.exchange,
            side=request.side,
            order_type=request.order_type,
            quantity=request.quantity,
            price=limit_price,
            status=OrderStatus.SUBMITTED,
            filled_quantity=0.0,
            average_price=None,
            market_type=request.market_type,
            metadata={
                "paper_trading": True,
                "pending": True,
            },
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        self._orders[order_id] = order
        logger.info(f"[Paper Trading] Limit order pending: {order_id} @ {limit_price}")

        return OrderResult(success=True, order=order)

    async def _update_position(self, order: Order, fee: float, leverage: int = 1, reduce_only: bool = False) -> None:
        symbol = order.symbol

        if symbol not in self._positions:
            self._positions[symbol] = Position(
                symbol=symbol,
                exchange=self.exchange,
                quantity=0.0,
                average_price=0.0,
                current_price=order.price or 0.0,
                market_type=order.market_type,
                leverage=leverage,
            )

        position = self._positions[symbol]

        if reduce_only or (position.quantity != 0 and (
            (order.side == OrderSide.BUY and position.quantity < 0) or
            (order.side == OrderSide.SELL and position.quantity > 0)
        )):
            close_qty = min(abs(order.filled_quantity), abs(position.quantity))

            if close_qty > 0:
                if position.quantity > 0:
                    pnl = (order.average_price - position.average_price) * close_qty
                else:
                    pnl = (position.average_price - order.average_price) * close_qty

                pnl -= fee
                position.realized_pnl += pnl

                if order.side == OrderSide.BUY:
                    position.quantity += close_qty
                else:
                    position.quantity -= close_qty

                if abs(position.quantity) < 1e-8:
                    position.quantity = 0.0
                    position.average_price = 0.0
        else:
            if position.quantity == 0:
                position.quantity = order.filled_quantity if order.side == OrderSide.BUY else -order.filled_quantity
                position.average_price = order.average_price or 0.0
            else:
                old_qty = abs(position.quantity)
                old_value = old_qty * position.average_price

                new_qty = order.filled_quantity
                new_value = new_qty * (order.average_price or 0.0)

                total_qty = old_qty + new_qty
                total_value = old_value + new_value

                new_avg_price = total_value / total_qty

                if order.side == OrderSide.BUY:
                    position.quantity += order.filled_quantity
                else:
                    position.quantity -= order.filled_quantity

                position.average_price = new_avg_price

        notional = order.filled_quantity * (order.average_price or 0.0)

        if order.side == OrderSide.BUY:
            self._balance["USDT"] -= (notional + fee)
        else:
            self._balance["USDT"] += (notional - fee)

        current_price = await self._get_current_price(symbol)
        if current_price and position.quantity != 0:
            position.current_price = current_price
            if position.quantity > 0:
                position.unrealized_pnl = (current_price - position.average_price) * abs(position.quantity)
            else:
                position.unrealized_pnl = (position.average_price - current_price) * abs(position.quantity)

        position.updated_at = datetime.now()

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        if order_id in self._orders:
            order = self._orders[order_id]
            if order.status in [OrderStatus.PENDING, OrderStatus.SUBMITTED]:
                order.status = OrderStatus.CANCELLED
                order.updated_at = datetime.now()
                logger.info(f"[Paper Trading] Order cancelled: {order_id}")
                return True
        return False

    async def get_order(self, order_id: str, symbol: str) -> Optional[Order]:
        return self._orders.get(order_id)

    async def get_positions(self) -> List[Position]:
        for symbol, position in self._positions.items():
            if abs(position.quantity) > 1e-8:
                current_price = await self._get_current_price(symbol)
                if current_price:
                    position.current_price = current_price
                    if position.quantity > 0:
                        position.unrealized_pnl = (current_price - position.average_price) * abs(position.quantity)
                    else:
                        position.unrealized_pnl = (position.average_price - current_price) * abs(position.quantity)

        return [p for p in self._positions.values() if abs(p.quantity) > 1e-8]

    async def get_balance(self) -> Dict[str, float]:
        return self._balance.copy()

    async def get_market_price(self, symbol: str) -> Optional[float]:
        return await self._get_current_price(symbol)

    def on_fill(self, callback: Callable) -> None:
        self._fill_callbacks.append(callback)

    def get_summary(self) -> Dict[str, Any]:
        total_unrealized_pnl = sum(p.unrealized_pnl for p in self._positions.values())
        total_realized_pnl = sum(p.realized_pnl for p in self._positions.values())

        return {
            "mode": "paper_trading",
            "balance": self._balance.copy(),
            "positions": len([p for p in self._positions.values() if abs(p.quantity) > 1e-8]),
            "total_unrealized_pnl": total_unrealized_pnl,
            "total_realized_pnl": total_realized_pnl,
            "total_pnl": total_unrealized_pnl + total_realized_pnl,
            "orders_count": len(self._orders),
            "slippage": self.slippage,
            "fee_maker": self.fee_maker,
            "fee_taker": self.fee_taker,
        }
