"""Execution Queries - 执行状态查询"""
from typing import Dict, Any

async def get_execution_state() -> Dict[str, Any]:
    from runtime.execution_runtime.runtime import get_execution_runtime
    runtime = get_execution_runtime()
    if runtime and hasattr(runtime, 'get_state'):
        return runtime.get_state()
    return {}

async def get_orders() -> Dict[str, Any]:
    from runtime.execution_runtime.runtime import get_execution_runtime
    runtime = get_execution_runtime()
    if runtime and hasattr(runtime, 'get_orders'):
        return runtime.get_orders()
    return {}
