"""Execution Queries - 执行状态查询入口

API Router 只调此模块，不直接碰 runtime/services/infrastructure。
"""
from typing import Dict, Any, List, Optional

import logging

logger = logging.getLogger(__name__)


async def get_execution_state() -> Dict[str, Any]:
    # TODO: migrate to new runtime architecture - runtime.execution_runtime removed
    # from runtime.execution_runtime.runtime import get_execution_runtime
    # runtime = get_execution_runtime()
    # if runtime and hasattr(runtime, 'get_state'):
    #     return runtime.get_state()
    return {}


async def get_orders(
    symbol: Optional[str] = None,
    exchange: Optional[str] = None,
    status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    state = await get_execution_state()
    orders = state.get("orders", {})
    result = list(orders.values())
    if symbol:
        result = [o for o in result if o.get("symbol") == symbol]
    if exchange:
        result = [o for o in result if o.get("exchange") == exchange]
    if status:
        result = [o for o in result if o.get("status") == status]
    return result


async def get_open_orders(
    symbol: Optional[str] = None,
    exchange: Optional[str] = None,
) -> List[Dict[str, Any]]:
    state = await get_execution_state()
    orders = state.get("orders", {})
    result = [
        o for o in orders.values()
        if o.get("status") in ("pending", "partially_filled", "new")
    ]
    if symbol:
        result = [o for o in result if o.get("symbol") == symbol]
    if exchange:
        result = [o for o in result if o.get("exchange") == exchange]
    return result


async def get_order(order_id: str) -> Optional[Dict[str, Any]]:
    state = await get_execution_state()
    orders = state.get("orders", {})
    return orders.get(order_id)
