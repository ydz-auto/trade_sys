"""Feature Queries - 特征状态查询"""
from typing import Dict, Any

async def get_feature_state() -> Dict[str, Any]:
    from runtime.feature_runtime import get_feature_runtime
    runtime = get_feature_runtime()
    if runtime and hasattr(runtime, 'get_state'):
        return runtime.get_state()
    return {}

async def get_feature_matrix_state() -> Dict[str, Any]:
    from runtime.feature_matrix_runtime import get_feature_matrix_runtime
    runtime = get_feature_matrix_runtime()
    if runtime and hasattr(runtime, 'get_state'):
        return runtime.get_state()
    return {}
