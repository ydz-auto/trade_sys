"""Replay Queries - 回放状态查询"""
from typing import Dict, Any, Optional

async def get_replay_state() -> Dict[str, Any]:
    from runtime.replay_runtime import get_replay_runtime
    runtime = get_replay_runtime()
    if runtime and hasattr(runtime, 'get_state'):
        return runtime.get_state()
    return {}

async def get_replay_sessions() -> list:
    from runtime.replay_runtime import get_replay_runtime
    runtime = get_replay_runtime()
    if runtime and hasattr(runtime, 'get_sessions'):
        return runtime.get_sessions()
    return []
