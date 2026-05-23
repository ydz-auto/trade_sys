"""
Execution API Service - 执行引擎 API 服务

职责边界（Service 层）：
- HTTP 参数校验
- 格式转换
- 委托执行 → ExecutionRuntime

禁止在 Service 层维护：
- _orders 字典（state）
- _positions 字典（state）
- ExecutionState 枚举（state）

状态来源：
- ExecutionRuntime（执行状态）
- PortfolioRuntime（持仓状态）
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
from domain.logging import get_logger
from application.queries.domain_queries import (
    get_order_side_enum,
    get_order_type_enum,
    get_exchange_enum,
    get_market_type_enum,
    get_order_status_enum,
    get_order_request_class,
)

OrderSide = get_order_side_enum()
OrderType = get_order_type_enum()
Exchange = get_exchange_enum()
MarketType = get_market_type_enum()
OrderStatus = get_order_status_enum()
OrderRequest = get_order_request_class()

logger = get_logger("execution_api_service")


class ExecutionAPIService:

    def __init__(self):
        pass

    async def create_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "market",
        price: Optional[float] = None,
        exchange: str = "binance",
    ) -> Dict[str, Any]:
        try:
            order_side = OrderSide(side.lower())
        except ValueError:
            return {"success": False, "error": f"Invalid side: {side}"}

        try:
            order_type_enum = OrderType(order_type.lower())
        except ValueError:
            return {"success": False, "error": f"Invalid order_type: {order_type}"}

        try:
            exchange_enum = Exchange(exchange.lower())
        except ValueError:
            return {"success": False, "error": f"Invalid exchange: {exchange}"}

        request = OrderRequest(
            symbol=symbol,
            exchange=exchange_enum,
            side=order_side,
            order_type=order_type_enum,
            quantity=quantity,
            price=price,
            market_type=MarketType.SPOT,
        )

        try:
            from application.commands.bus_commands import safe_execute_order, get_execution_blocked_error
            ExecutionBlockedError = get_execution_blocked_error()
            result = await safe_execute_order(request)
        except ExecutionBlockedError as e:
            return {"success": False, "error": str(e), "reason": e.reason}
        except Exception as e:
            return {"success": False, "error": str(e)}

        if not result.success:
            return {"success": False, "error": result.error}

        if result.order:
            order_dict = result.order.to_dict()
            return order_dict

        return {"success": True}

    async def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        from application.queries.execution import get_execution_state

        try:
            state = await get_execution_state()
            orders = state.get("orders", {})
            return orders.get(order_id)
        except Exception:
            return None

    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        from application.commands.bus_commands import publish_command

        await publish_command(
            command_type="cancel_order",
            data={"order_id": order_id},
            target="execution_runtime",
        )
        return {"success": True, "order_id": order_id, "dispatch_via": "runtime_bus"}

    async def get_open_orders(
        self,
        symbol: Optional[str] = None,
        exchange: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        from application.queries.execution import get_execution_state

        try:
            state = await get_execution_state()
            orders = state.get("orders", {})
            open_orders = [
                o for o in orders.values()
                if o["status"] in (OrderStatus.PENDING.value, OrderStatus.PARTIALLY_FILLED.value)
            ]
            if symbol:
                open_orders = [o for o in open_orders if o["symbol"] == symbol]
            if exchange:
                open_orders = [o for o in open_orders if o.get("exchange") == exchange]
            return open_orders
        except Exception:
            return []

    async def get_order_history(
        self,
        symbol: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        from application.queries.execution import get_execution_state

        try:
            state = await get_execution_state()
            orders = state.get("orders", {})
            all_orders = list(orders.values())
            if symbol:
                all_orders = [o for o in all_orders if o["symbol"] == symbol]
            all_orders.sort(key=lambda x: x["created_at"], reverse=True)
            return all_orders[:limit]
        except Exception:
            return []

    async def get_positions(
        self,
        symbol: Optional[str] = None,
        exchange: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        from application.queries.portfolio import get_portfolio_state

        try:
            state = await get_portfolio_state()
            positions = state.get("positions", [])
            if symbol:
                positions = [p for p in positions if p["symbol"] == symbol]
            if exchange:
                positions = [p for p in positions if p.get("exchange") == exchange]
            return positions
        except Exception:
            return []

    async def close_position(
        self,
        position_id: str,
        quantity: Optional[float] = None,
    ) -> Dict[str, Any]:
        from application.commands.bus_commands import publish_command

        await publish_command(
            command_type="close_position",
            data={"position_id": position_id, "quantity": quantity},
            target="portfolio_runtime",
        )
        return {"success": True, "position_id": position_id, "dispatch_via": "runtime_bus"}

    async def update_position(
        self,
        position_id: str,
        updates: Dict[str, Any],
    ) -> Dict[str, Any]:
        from application.commands.bus_commands import publish_command

        await publish_command(
            command_type="update_position",
            data={"position_id": position_id, "updates": updates},
            target="portfolio_runtime",
        )
        return {"success": True, "position_id": position_id, "dispatch_via": "runtime_bus"}

    async def execute_signal(
        self,
        signal_id: str,
        symbol: str,
        action: str,
        quantity: float,
        confidence: float = 1.0,
        exchange: str = "binance",
    ) -> Dict[str, Any]:
        try:
            order_side = OrderSide(action.lower())
        except ValueError:
            return {"success": False, "error": f"Invalid action: {action}"}

        try:
            exchange_enum = Exchange(exchange.lower())
        except ValueError:
            exchange_enum = Exchange.BINANCE

        request = OrderRequest(
            symbol=symbol,
            exchange=exchange_enum,
            side=order_side,
            order_type=OrderType.MARKET,
            quantity=quantity,
            market_type=MarketType.SPOT,
        )

        try:
            from application.commands.bus_commands import safe_execute_order, get_execution_blocked_error
            ExecutionBlockedError = get_execution_blocked_error()
            result = await safe_execute_order(request)
        except ExecutionBlockedError as e:
            return {
                "success": False,
                "signal_id": signal_id,
                "error": str(e),
                "reason": e.reason,
            }
        except Exception as e:
            return {
                "success": False,
                "signal_id": signal_id,
                "error": str(e),
            }

        if not result.success:
            return {
                "success": False,
                "signal_id": signal_id,
                "error": result.error,
            }

        if result.order:
            return {
                "success": True,
                "signal_id": signal_id,
                "order_id": result.order.order_id,
                "symbol": symbol,
                "action": action,
                "quantity": quantity,
                "confidence": confidence,
            }

        return {"success": True, "signal_id": signal_id}

    async def execute_signals_batch(
        self,
        signals: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
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
                if result.get("success"):
                    results.append(result)
                else:
                    errors.append({
                        "signal": signal,
                        "error": result.get("error", "Unknown error"),
                    })
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
        from application.queries.execution import get_execution_state
        from application.queries.portfolio import get_portfolio_state

        try:
            exec_state = await get_execution_state()
            portfolio_state = await get_portfolio_state()
            return {
                "state": exec_state.get("state", "unknown"),
                "last_error": exec_state.get("last_error"),
                "orders_count": len(exec_state.get("orders", {})),
                "positions_count": len(portfolio_state.get("positions", [])),
                "source": "runtime",
            }
        except Exception:
            return {
                "state": "unknown",
                "source": "runtime_bus_unavailable",
            }


_execution_api_service: Optional[ExecutionAPIService] = None


def get_execution_api_service() -> ExecutionAPIService:
    global _execution_api_service
    if _execution_api_service is None:
        _execution_api_service = ExecutionAPIService()
    return _execution_api_service
