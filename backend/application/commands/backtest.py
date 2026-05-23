"""Backtest Commands - 回测写操作"""
from typing import Dict, Any, Optional

async def start_backtest(config: Dict[str, Any]) -> Dict[str, Any]:
    from runtime.replay_runtime import get_replay_runtime
    runtime = get_replay_runtime()
    if runtime and hasattr(runtime, 'start_session'):
        return await runtime.start_session(config)
    return {"success": False, "error": "ReplayRuntime not available"}

async def stop_backtest(session_id: str) -> Dict[str, Any]:
    from runtime.replay_runtime import get_replay_runtime
    runtime = get_replay_runtime()
    if runtime and hasattr(runtime, 'stop_session'):
        return await runtime.stop_session(session_id)
    return {"success": False, "error": "ReplayRuntime not available"}
