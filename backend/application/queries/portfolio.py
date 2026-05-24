"""Portfolio Queries - 组合状态查询入口

API Router 只调此模块，不直接碰 runtime/services/infrastructure。
所有查询通过 portfolio_runtime 的公共 API。
"""
from typing import Dict, Any, List, Optional

import logging

logger = logging.getLogger(__name__)


async def get_portfolio_state() -> Dict[str, Any]:
    from runtimes.portfolio_runtime import get_portfolio_runtime
    runtime = get_portfolio_runtime()
    if runtime and hasattr(runtime, 'get_state'):
        return runtime.get_state()
    return {}


async def get_positions(symbol: Optional[str] = None, exchange: Optional[str] = None) -> List[Dict[str, Any]]:
    state = await get_portfolio_state()
    positions = state.get("positions", [])
    if symbol:
        positions = [p for p in positions if p.get("symbol") == symbol]
    if exchange:
        positions = [p for p in positions if p.get("exchange") == exchange]
    return positions


async def get_accounts() -> Dict[str, Any]:
    state = await get_portfolio_state()
    return state.get("accounts", {})


async def get_exposure() -> Dict[str, Any]:
    from runtimes.portfolio_runtime import get_portfolio_runtime
    runtime = get_portfolio_runtime()
    if runtime and hasattr(runtime, 'get_exposure_summary'):
        return await runtime.get_exposure_summary()
    return {}


async def get_exposure_warnings() -> List[Dict[str, Any]]:
    from runtimes.portfolio_runtime import get_portfolio_runtime
    runtime = get_portfolio_runtime()
    if runtime and hasattr(runtime, 'get_exposure_warnings'):
        return await runtime.get_exposure_warnings()
    return []


async def get_portfolio_metrics() -> Dict[str, Any]:
    from runtimes.portfolio_runtime import get_portfolio_runtime
    runtime = get_portfolio_runtime()
    if runtime and hasattr(runtime, 'get_portfolio_metrics'):
        metrics = await runtime.get_portfolio_metrics()
        if metrics and hasattr(metrics, 'to_dict'):
            return metrics.to_dict()
    return {}


async def get_risk_budget(daily_pnl: float = 0.0) -> Dict[str, float]:
    from runtimes.portfolio_runtime import get_portfolio_runtime
    runtime = get_portfolio_runtime()
    if runtime and hasattr(runtime, 'get_risk_budget'):
        return await runtime.get_risk_budget(daily_pnl=daily_pnl)
    return {}


async def get_trading_status() -> Dict[str, Any]:
    from application.queries.execution import get_execution_state

    portfolio_state = await get_portfolio_state()
    exec_state = await get_execution_state()

    positions = portfolio_state.get("positions", [])
    accounts = portfolio_state.get("accounts", {})
    orders = exec_state.get("orders", {})

    total_equity = sum(
        acc.get("balance", 0) + acc.get("unrealized_pnl", 0)
        for acc in accounts.values()
    )
    total_unrealized_pnl = sum(p.get("unrealized_pnl", 0) for p in positions)
    total_position_value = sum(
        p["quantity"] * p.get("current_price", p.get("entry_price", 0))
        for p in positions
    )

    return {
        "mode": "runtime",
        "total_equity": round(total_equity, 2),
        "total_unrealized_pnl": round(total_unrealized_pnl, 2),
        "total_position_value": round(total_position_value, 2),
        "positions_count": len(positions),
        "open_orders_count": len([
            o for o in orders.values()
            if o.get("status") not in ("filled", "cancelled")
        ]),
        "state_source": "portfolio_runtime",
    }
