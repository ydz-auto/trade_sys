"""Correlation Queries - 相关性状态查询"""
from typing import Dict, Any

async def get_correlation_state() -> Dict[str, Any]:
    from runtime.correlation_runtime.runtime import get_correlation_runtime
    runtime = get_correlation_runtime()
    if runtime and hasattr(runtime, 'get_state'):
        return runtime.get_state()
    return {}
