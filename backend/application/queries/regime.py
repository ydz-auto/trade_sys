"""Regime Queries - 市场状态查询"""
from typing import Dict, Any

async def get_regime_state() -> Dict[str, Any]:
    from runtime.regime_runtime import get_regime_runtime
    runtime = get_regime_runtime()
    if runtime and hasattr(runtime, 'get_state'):
        return runtime.get_state()
    return {}
