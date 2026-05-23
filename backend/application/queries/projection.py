"""Projection Queries - 投影状态查询"""
from typing import Dict, Any

async def get_projection_state() -> Dict[str, Any]:
    from runtime.projection_runtime.runtime import get_projection_runtime
    runtime = get_projection_runtime()
    if runtime and hasattr(runtime, 'get_state'):
        return runtime.get_state()
    return {}
