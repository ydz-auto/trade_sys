"""
Execution API Service - 执行引擎 API 服务

职责：
- 订单管理
- 持仓管理
- 信号执行
- 执行状态
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import uuid
from infrastructure.logging import get_logger

logger = get_logger("execution_api_service")


class OrderStatus(Enum):
    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class ExecutionState(Enum):
    IDLE = "idle"
    EXECUTING = "executing"
    ERROR = "error"


class ExecutionAPIService:
    """执行引擎 API 服务"""

    def __init__(self):
        self._orders: Dict[str, Dict] = {}
        self._positions: Dict[str, Dict] = {}
        self._execution_state = ExecutionState.IDLE
        self._last_error: Optional[str] = None

    async def create_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "market",
        price: Optional[float] = None,
        exchange: str = "binance",
    ) -> Dict[str, Any]:
        """
        创建订单

        Args:
            symbol: 交易对
            side: 方向 buy/sell
            quantity: 数量
            order_type: 订单类型 market/limit
            price: 价格（限价单需要）
            exchange: 交易所

        Returns:
            订单信息
        """
        order_id = f"ord_{uuid.uuid4().hex[:12]}"

        order = {
            "order_id": order_id,
            "symbol": symbol,
            "side": side.upper(),
            "quantity": quantity,
            "order_type": order_type,
            "price": price,
            "exchange": exchange,
            "status": OrderStatus.PENDING.value,
            "filled_quantity": 0,
            "average_price": 0,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        self._orders[order_id] = order

        self._execution_state = ExecutionState.EXECUTING

        return order

    async def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """获取订单详情"""
        return self._orders.get(order_id)

    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """取消订单"""
        if order_id not in self._orders:
            return {"success": False, "error": "Order not found"}

        order = self._orders[order_id]
        if order["status"] in (OrderStatus.FILLED.value, OrderStatus.CANCELLED.value):
            return {"success": False, "error": f"Cannot cancel order with status: {order['status']}"}

        order["status"] = OrderStatus.CANCELLED.value
        order["updated_at"] = datetime.now().isoformat()

        return {"success": True, "order_id": order_id}

    async def get_open_orders(
        self,
        symbol: Optional[str] = None,
        exchange: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """获取未完成订单"""
        orders = [
            o for o in self._orders.values()
            if o["status"] in (OrderStatus.PENDING.value, OrderStatus.PARTIALLY_FILLED.value)
        ]

        if symbol:
            orders = [o for o in orders if o["symbol"] == symbol]
        if exchange:
            orders = [o for o in orders if o.get("exchange") == exchange]

        return orders

    async def get_order_history(
        self,
        symbol: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """获取订单历史"""
        orders = list(self._orders.values())

        if symbol:
            orders = [o for o in orders if o["symbol"] == symbol]

        orders.sort(key=lambda x: x["created_at"], reverse=True)
        return orders[:limit]

    async def get_positions(
        self,
        symbol: Optional[str] = None,
        exchange: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """获取持仓列表"""
        positions = list(self._positions.values())

        if symbol:
            positions = [p for p in positions if p["symbol"] == symbol]
        if exchange:
            positions = [p for p in positions if p.get("exchange") == exchange]

        return positions

    async def close_position(
        self,
        position_id: str,
        quantity: Optional[float] = None,
    ) -> Dict[str, Any]:
        """平仓"""
        if position_id not in self._positions:
            return {"success": False, "error": "Position not found"}

        position = self._positions[position_id]
        position["status"] = "closed"
        position["closed_at"] = datetime.now().isoformat()

        return {
            "success": True,
            "position_id": position_id,
            "symbol": position["symbol"],
        }

    async def update_position(
        self,
        position_id: str,
        updates: Dict[str, Any],
    ) -> Dict[str, Any]:
        """更新持仓"""
        if position_id not in self._positions:
            return {"success": False, "error": "Position not found"}

        position = self._positions[position_id]
        position.update(updates)
        position["updated_at"] = datetime.now().isoformat()

        return {"success": True, "position": position}

    async def execute_signal(
        self,
        signal_id: str,
        symbol: str,
        action: str,
        quantity: float,
        confidence: float = 1.0,
        exchange: str = "binance",
    ) -> Dict[str, Any]:
        """
        执行信号

        Args:
            signal_id: 信号ID
            symbol: 币种
            action: 操作 buy/sell
            quantity: 数量
            confidence: 置信度
            exchange: 交易所

        Returns:
            执行结果
        """
        self._execution_state = ExecutionState.EXECUTING

        order = await self.create_order(
            symbol=symbol,
            side=action,
            quantity=quantity,
            exchange=exchange,
        )

        self._execution_state = ExecutionState.IDLE

        return {
            "success": True,
            "signal_id": signal_id,
            "order_id": order["order_id"],
            "symbol": symbol,
            "action": action,
            "quantity": quantity,
            "confidence": confidence,
        }

    async def execute_signals_batch(
        self,
        signals: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """批量执行信号"""
        results = []
        errors = []

        for signal in signals:
            try:
                result = await self.execute_signal(
                    signal_id=signal.get("signal_id", ""),
                    symbol=signal["symbol"],
                    action=signal["action"],
                    quantity=signal["quantity"],
                    confidence=signal.get("confidence", 1.0),
                    exchange=signal.get("exchange", "binance"),
                )
                results.append(result)
            except Exception as e:
                errors.append({
                    "signal": signal,
                    "error": str(e),
                })

        return {
            "total": len(signals),
            "executed": len(results),
            "failed": len(errors),
            "results": results,
            "errors": errors,
        }

    async def get_execution_state(self) -> Dict[str, Any]:
        """获取执行状态"""
        return {
            "state": self._execution_state.value,
            "last_error": self._last_error,
            "orders_count": len(self._orders),
            "open_orders_count": len([
                o for o in self._orders.values()
                if o["status"] in (OrderStatus.PENDING.value, OrderStatus.PARTIALLY_FILLED.value)
            ]),
            "positions_count": len(self._positions),
        }

    def update_position_from_order(self, order: Dict[str, Any]):
        """根据订单更新持仓"""
        if order["status"] != OrderStatus.FILLED.value:
            return

        position_id = f"{order['symbol']}_{order['side']}"
        symbol = order["symbol"]
        side = order["side"]
        quantity = order["filled_quantity"]
        price = order.get("average_price", 0)

        if position_id in self._positions:
            position = self._positions[position_id]
            if side == OrderSide.BUY.value:
                position["quantity"] += quantity
                position["entry_price"] = (
                    position["entry_price"] * (position["quantity"] - quantity) + price * quantity
                ) / position["quantity"]
            else:
                position["quantity"] -= quantity
        else:
            self._positions[position_id] = {
                "position_id": position_id,
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "entry_price": price,
                "current_price": price,
                "unrealized_pnl": 0,
                "exchange": order.get("exchange", "binance"),
                "status": "open",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }


_execution_api_service: Optional[ExecutionAPIService] = None


def get_execution_api_service() -> ExecutionAPIService:
    """获取执行 API 服务实例"""
    global _execution_api_service
    if _execution_api_service is None:
        _execution_api_service = ExecutionAPIService()
    return _execution_api_service
