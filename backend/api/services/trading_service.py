"""
Trading Service - 交易服务

职责边界（Service 层）：
- adapter（格式转换、参数校验）
- 调用 PortfolioRuntime 进行 position/account 操作
- 不维护 position/account state

禁止在 Service 层维护：
- trading:positions（position truth）
- trading:accounts（account truth）
- PnL 计算逻辑
- SL/TP 检查逻辑
- position lifecycle

状态来源：
- PortfolioRuntime（持仓、账户 truth）
"""
from typing import Dict, List, Optional, Any
from datetime import datetime

from infrastructure.cache.redis_client import RedisClient, init_redis
from infrastructure.logging import get_logger

logger = get_logger("trading_service")


class TradingService:

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

    async def get_positions(self) -> List[Dict]:
        from runtime.bus.runtime_bus import get_runtime_bus

        bus = get_runtime_bus()
        try:
            state = bus.get_state("portfolio")
            return state.get("positions", [])
        except Exception:
            return []

    async def get_accounts(self) -> Dict:
        from runtime.bus.runtime_bus import get_runtime_bus

        bus = get_runtime_bus()
        try:
            state = bus.get_state("portfolio")
            return state.get("accounts", {})
        except Exception:
            return {}

    async def get_open_orders(self) -> List[Dict]:
        from runtime.bus.runtime_bus import get_runtime_bus

        bus = get_runtime_bus()
        try:
            state = bus.get_state("execution")
            orders = state.get("orders", {})
            return [
                o for o in orders.values()
                if o.get("status") not in ("filled", "cancelled")
            ]
        except Exception:
            return []

    async def place_order(self, order_data: Dict) -> Dict:
        from runtime.bus.runtime_bus import get_runtime_bus
        from domain.execution.models import OrderSide, OrderType as DomainOrderType, MarketType, Exchange

        bus = get_runtime_bus()

        order_id = f"ord_{datetime.now().timestamp()}"
        symbol = order_data["symbol"]
        side = order_data["side"]
        quantity = order_data["quantity"]
        exchange = order_data.get("exchange", "binance")
        market_type = order_data.get("market_type", "spot")

        await bus.publish_command(
            command="create_order",
            target="execution_runtime",
            params={
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "exchange": exchange,
                "market_type": market_type,
                "order_type": order_data.get("order_type", "market"),
                "price": order_data.get("price"),
                "leverage": order_data.get("leverage", 1),
                "client_order_id": order_id,
            },
            source="api.trading",
        )

        return {
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "status": "pending",
            "dispatch_via": "runtime_bus",
            "target": "execution_runtime",
        }

    async def close_position(self, close_data: Dict) -> Dict:
        from runtime.bus.runtime_bus import get_runtime_bus

        bus = get_runtime_bus()

        symbol = close_data["symbol"]
        quantity = close_data.get("quantity")

        positions = await self.get_positions()
        position_id = None
        for pos in positions:
            if pos["symbol"] == symbol:
                position_id = pos.get("position_id")
                break

        if not position_id:
            raise ValueError(f"Position not found for {symbol}")

        await bus.publish_command(
            command="close_position",
            target="portfolio_runtime",
            params={
                "position_id": position_id,
                "quantity": quantity,
            },
            source="api.trading",
        )

        return {
            "success": True,
            "position_id": position_id,
            "dispatch_via": "runtime_bus",
            "target": "portfolio_runtime",
        }

    async def set_leverage(self, data: Dict) -> Dict:
        from runtime.bus.runtime_bus import get_runtime_bus

        bus = get_runtime_bus()
        symbol = data["symbol"]
        leverage = data["leverage"]

        positions = await self.get_positions()
        position_id = None
        for pos in positions:
            if pos["symbol"] == symbol:
                position_id = pos.get("position_id")
                break

        if not position_id:
            raise ValueError(f"Position not found for {symbol}")

        await bus.publish_command(
            command="set_leverage",
            target="portfolio_runtime",
            params={
                "position_id": position_id,
                "leverage": leverage,
            },
            source="api.trading",
        )

        return {
            "success": True,
            "symbol": symbol,
            "leverage": leverage,
            "dispatch_via": "runtime_bus",
            "target": "portfolio_runtime",
        }

    async def set_stop_loss_take_profit(self, data: Dict) -> Dict:
        from runtime.bus.runtime_bus import get_runtime_bus

        bus = get_runtime_bus()
        symbol = data["symbol"]

        positions = await self.get_positions()
        position_id = None
        for pos in positions:
            if pos["symbol"] == symbol:
                position_id = pos.get("position_id")
                break

        if not position_id:
            raise ValueError(f"Position not found for {symbol}")

        await bus.publish_command(
            command="set_stop_loss_take_profit",
            target="portfolio_runtime",
            params={
                "position_id": position_id,
                "stop_loss_pct": data.get("stop_loss_pct"),
                "take_profit_pct": data.get("take_profit_pct"),
                "stop_loss_price": data.get("stop_loss_price"),
                "take_profit_price": data.get("take_profit_price"),
            },
            source="api.trading",
        )

        return {
            "success": True,
            "position_id": position_id,
            "dispatch_via": "runtime_bus",
            "target": "portfolio_runtime",
        }

    async def adjust_position(self, data: Dict) -> Dict:
        from runtime.bus.runtime_bus import get_runtime_bus

        bus = get_runtime_bus()
        symbol = data["symbol"]

        positions = await self.get_positions()
        position_id = None
        for pos in positions:
            if pos["symbol"] == symbol:
                position_id = pos.get("position_id")
                break

        if not position_id:
            raise ValueError(f"Position not found for {symbol}")

        await bus.publish_command(
            command="adjust_position",
            target="portfolio_runtime",
            params={
                "position_id": position_id,
                "new_quantity": data.get("new_quantity"),
                "new_leverage": data.get("new_leverage"),
            },
            source="api.trading",
        )

        return {
            "success": True,
            "position_id": position_id,
            "dispatch_via": "runtime_bus",
            "target": "portfolio_runtime",
        }

    async def get_trading_status(self) -> Dict:
        from runtime.bus.runtime_bus import get_runtime_bus

        bus = get_runtime_bus()

        try:
            portfolio_state = bus.get_state("portfolio")
            exec_state = bus.get_state("execution")
        except Exception:
            portfolio_state = {}
            exec_state = {}

        positions = portfolio_state.get("positions", [])
        accounts = portfolio_state.get("accounts", {})
        orders = exec_state.get("orders", {})

        total_equity = sum(acc.get("balance", 0) + acc.get("unrealized_pnl", 0) for acc in accounts.values())
        total_unrealized_pnl = sum(p.get("unrealized_pnl", 0) for p in positions)
        total_position_value = sum(p["quantity"] * p.get("current_price", p["entry_price"]) for p in positions)

        return {
            "mode": "runtime",
            "total_equity": round(total_equity, 2),
            "total_unrealized_pnl": round(total_unrealized_pnl, 2),
            "total_position_value": round(total_position_value, 2),
            "positions_count": len(positions),
            "open_orders_count": len([o for o in orders.values() if o.get("status") not in ("filled", "cancelled")]),
            "state_source": "portfolio_runtime",
            "timestamp": datetime.now().isoformat(),
        }

    async def health_check(self) -> Dict:
        from runtime.bus.runtime_bus import get_runtime_bus

        bus = get_runtime_bus()
        try:
            await bus.publish_command(
                command="health_check",
                target="portfolio_runtime",
                params={},
                source="api.trading",
            )
            return {
                "status": "healthy",
                "state_source": "portfolio_runtime",
                "timestamp": datetime.now().isoformat(),
            }
        except Exception:
            return {
                "status": "degraded",
                "state_source": "unavailable",
                "timestamp": datetime.now().isoformat(),
            }


_trading_service: Optional[TradingService] = None


def get_trading_service() -> TradingService:
    global _trading_service
    if _trading_service is None:
        _trading_service = TradingService()
    return _trading_service
