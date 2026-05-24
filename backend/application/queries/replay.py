from typing import Dict, Any, Optional, List

_BACKTEST_KEY_PREFIX = "backtest:"


async def get_replay_state() -> Dict[str, Any]:
    from runtimes.replay_runtime.runtime import get_replay_runtime
    runtime = get_replay_runtime()
    if runtime and hasattr(runtime, 'get_state'):
        return runtime.get_state()
    return {}


async def get_replay_sessions() -> list:
    from runtimes.replay_runtime.runtime import get_replay_runtime
    runtime = get_replay_runtime()
    if runtime and hasattr(runtime, 'get_sessions'):
        return runtime.get_sessions()
    return []


async def get_replay_status(replay_id: str) -> Optional[Dict[str, Any]]:
    from application.commands.backtest import _replay_sessions
    return _replay_sessions.get(replay_id)


async def list_replays() -> List[Dict[str, Any]]:
    from application.commands.backtest import _replay_sessions
    return list(_replay_sessions.values())


async def get_backtest(backtest_id: str) -> Optional[Dict[str, Any]]:
    from application.queries.infrastructure_queries import init_redis
    redis = await init_redis()
    if redis is None:
        return None
    return await redis.get_json(f"{_BACKTEST_KEY_PREFIX}{backtest_id}")


async def list_backtests() -> List[Dict[str, Any]]:
    from application.queries.infrastructure_queries import init_redis
    redis = await init_redis()
    if redis is None:
        return []
    keys = await redis.client.keys(f"{_BACKTEST_KEY_PREFIX}*")
    results = []
    for key in keys:
        data = await redis.get_json(key)
        if data:
            results.append(data)
    return sorted(results, key=lambda x: x.get("created_at", ""), reverse=True)
