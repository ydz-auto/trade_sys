"""Trading Commands - 交易写操作入口

API Router 只调此模块，不直接碰 runtime/services/infrastructure。
"""
from typing import Dict, Any, Optional
from datetime import datetime

import logging

logger = logging.getLogger(__name__)


async def submit_order(
    symbol: str,
    action: str,
    quantity: float,
    order_type: str = "market",
    price: Optional[float] = None,
    leverage: int = 1,
    exchange: str = "binance",
    market_type: str = "spot",
    **kwargs,
) -> Dict[str, Any]:
    from application.commands.bus_commands import publish_command

    order_id = f"ord_{datetime.utcnow().timestamp()}"
    await publish_command(
        command_type="create_order",
        data={
            "symbol": symbol,
            "side": action,
            "quantity": quantity,
            "exchange": exchange,
            "market_type": market_type,
            "order_type": order_type,
            "price": price,
            "leverage": leverage,
            "client_order_id": order_id,
        },
        target="execution_runtime",
    )
    return {
        "order_id": order_id,
        "symbol": symbol,
        "side": action,
        "quantity": quantity,
        "status": "pending",
        "dispatch_via": "runtime_bus",
        "target": "execution_runtime",
    }


async def cancel_order(order_id: str) -> Dict[str, Any]:
    from application.commands.bus_commands import publish_command

    await publish_command(
        command_type="cancel_order",
        data={"order_id": order_id},
        target="execution_runtime",
    )
    return {"success": True, "order_id": order_id, "dispatch_via": "runtime_bus"}


async def close_position(symbol: str, quantity: Optional[float] = None) -> Dict[str, Any]:
    from application.commands.bus_commands import publish_command
    from application.queries.portfolio import get_positions

    positions = await get_positions()
    position_id = None
    for pos in positions:
        if pos.get("symbol") == symbol:
            position_id = pos.get("position_id")
            break

    if not position_id:
        raise ValueError(f"Position not found for {symbol}")

    await publish_command(
        command_type="close_position",
        data={"position_id": position_id, "quantity": quantity},
        target="portfolio_runtime",
    )
    return {
        "success": True,
        "position_id": position_id,
        "dispatch_via": "runtime_bus",
        "target": "portfolio_runtime",
    }


async def set_leverage(symbol: str, leverage: int) -> Dict[str, Any]:
    from application.commands.bus_commands import publish_command
    from application.queries.portfolio import get_positions

    positions = await get_positions()
    position_id = None
    for pos in positions:
        if pos.get("symbol") == symbol:
            position_id = pos.get("position_id")
            break

    if not position_id:
        raise ValueError(f"Position not found for {symbol}")

    await publish_command(
        command_type="set_leverage",
        data={"position_id": position_id, "leverage": leverage},
        target="portfolio_runtime",
    )
    return {"success": True, "symbol": symbol, "leverage": leverage, "dispatch_via": "runtime_bus"}


async def set_stop_loss_take_profit(
    symbol: str,
    stop_loss_pct: Optional[float] = None,
    take_profit_pct: Optional[float] = None,
    stop_loss_price: Optional[float] = None,
    take_profit_price: Optional[float] = None,
) -> Dict[str, Any]:
    from application.commands.bus_commands import publish_command
    from application.queries.portfolio import get_positions

    positions = await get_positions()
    position_id = None
    for pos in positions:
        if pos.get("symbol") == symbol:
            position_id = pos.get("position_id")
            break

    if not position_id:
        raise ValueError(f"Position not found for {symbol}")

    await publish_command(
        command_type="set_stop_loss_take_profit",
        data={
            "position_id": position_id,
            "stop_loss_pct": stop_loss_pct,
            "take_profit_pct": take_profit_pct,
            "stop_loss_price": stop_loss_price,
            "take_profit_price": take_profit_price,
        },
        target="portfolio_runtime",
    )
    return {"success": True, "position_id": position_id, "dispatch_via": "runtime_bus"}


async def adjust_position(
    symbol: str,
    new_quantity: Optional[float] = None,
    new_leverage: Optional[int] = None,
) -> Dict[str, Any]:
    from application.commands.bus_commands import publish_command
    from application.queries.portfolio import get_positions

    positions = await get_positions()
    position_id = None
    for pos in positions:
        if pos.get("symbol") == symbol:
            position_id = pos.get("position_id")
            break

    if not position_id:
        raise ValueError(f"Position not found for {symbol}")

    await publish_command(
        command_type="adjust_position",
        data={
            "position_id": position_id,
            "new_quantity": new_quantity,
            "new_leverage": new_leverage,
        },
        target="portfolio_runtime",
    )
    return {"success": True, "position_id": position_id, "dispatch_via": "runtime_bus"}


async def check_stop_loss_take_profit() -> Dict[str, Any]:
    from application.commands.bus_commands import publish_command

    await publish_command(
        command_type="check_sl_tp",
        data={},
        target="portfolio_runtime",
    )
    return {"triggered": [], "count": 0, "dispatch_via": "runtime_bus"}
