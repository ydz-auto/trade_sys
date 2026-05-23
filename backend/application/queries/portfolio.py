"""Portfolio Queries - 组合状态查询"""
from typing import Dict, Any, Optional

async def get_portfolio_state() -> Dict[str, Any]:
    from runtime.portfolio_runtime import get_portfolio_runtime
    runtime = get_portfolio_runtime()
    if runtime and hasattr(runtime, 'get_state'):
        return runtime.get_state()
    return {}

async def get_positions() -> Dict[str, Any]:
    from runtime.portfolio_runtime import get_portfolio_runtime
    runtime = get_portfolio_runtime()
    if runtime and hasattr(runtime, 'get_positions'):
        return runtime.get_positions()
    return {}
