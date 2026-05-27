from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid

_BACKTEST_KEY_PREFIX = "backtest:"
_replay_sessions: Dict[str, Dict[str, Any]] = {}


async def start_backtest(config: Dict[str, Any]) -> Dict[str, Any]:
    from runtime.replay_runtime.runtime import get_replay_runtime
    runtime = get_replay_runtime()
    if runtime and hasattr(runtime, 'start_session'):
        return await runtime.start_session(config)
    return {"success": False, "error": "ReplayRuntime not available"}


async def stop_backtest(session_id: str) -> Dict[str, Any]:
    from runtime.replay_runtime.runtime import get_replay_runtime
    runtime = get_replay_runtime()
    if runtime and hasattr(runtime, 'stop_session'):
        return await runtime.stop_session(session_id)
    return {"success": False, "error": "ReplayRuntime not available"}


async def create_and_run_backtest(backtest_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
    from application.commands.bus_commands import publish_command
    from application.queries.infrastructure_queries import init_redis

    await publish_command(
        command_type="run_backtest",
        data={"backtest_id": backtest_id, **config},
        target="replay_runtime",
    )

    redis = await init_redis()
    await redis.set_json(f"{_BACKTEST_KEY_PREFIX}{backtest_id}", {
        "id": backtest_id,
        "status": "running",
        "config": config,
        "metrics": None,
        "trades": [],
        "equity_curve": [],
        "drawdown_curve": [],
        "created_at": datetime.now().isoformat(),
        "completed_at": None,
        "error_message": None,
    })
    return await redis.get_json(f"{_BACKTEST_KEY_PREFIX}{backtest_id}")


async def stop_backtest_task(backtest_id: str) -> Dict[str, Any]:
    from application.commands.bus_commands import publish_command
    from application.queries.infrastructure_queries import init_redis

    await publish_command(
        command_type="stop_backtest",
        data={"backtest_id": backtest_id},
        target="replay_runtime",
    )

    redis = await init_redis()
    backtest = await redis.get_json(f"{_BACKTEST_KEY_PREFIX}{backtest_id}")
    if not backtest:
        return {"success": False, "error": "Not found"}
    backtest["status"] = "stopped"
    backtest["completed_at"] = datetime.now().isoformat()
    await redis.set_json(f"{_BACKTEST_KEY_PREFIX}{backtest_id}", backtest)
    return {"success": True, "backtest_id": backtest_id}


async def create_replay(
    start_time: datetime,
    end_time: datetime,
    mode: str,
    symbols: List[str],
    exchanges: List[str],
    event_types: List[str],
    speed: float,
) -> Dict[str, Any]:
    from runtime.replay_runtime.runtime import get_replay_runtime

    replay_id = f"replay_{uuid.uuid4().hex[:8]}"
    now = datetime.now().isoformat()

    session_data = {
        "replay_id": replay_id,
        "status": "pending",
        "total_events": 0,
        "processed_events": 0,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "current_time": None,
        "error": None,
        "stats": {},
        "created_at": now,
        "completed_at": None,
        "_params": {
            "mode": mode,
            "symbols": symbols,
            "exchanges": exchanges,
            "event_types": event_types,
            "speed": speed,
        },
    }

    _replay_sessions[replay_id] = session_data

    runtime = get_replay_runtime()
    if runtime and hasattr(runtime, 'start_session'):
        try:
            await runtime.start_session(
                symbol=symbols[0] if symbols else "BTCUSDT",
                start_time_ms=int(start_time.timestamp() * 1000),
                end_time_ms=int(end_time.timestamp() * 1000),
            )
            session_data["status"] = "running"
        except Exception as e:
            session_data["status"] = "failed"
            session_data["error"] = str(e)

    return session_data


async def cancel_replay(replay_id: str) -> bool:
    from runtime.replay_runtime.runtime import get_replay_runtime

    session = _replay_sessions.get(replay_id)
    if not session:
        return False

    runtime = get_replay_runtime()
    if runtime and hasattr(runtime, 'stop'):
        await runtime.stop()

    session["status"] = "completed"
    session["completed_at"] = datetime.now().isoformat()
    return True


async def delete_replay(replay_id: str) -> bool:
    from runtime.replay_runtime.runtime import get_replay_runtime

    session = _replay_sessions.get(replay_id)
    if not session:
        return False

    runtime = get_replay_runtime()
    if runtime and hasattr(runtime, 'stop'):
        await runtime.stop()

    del _replay_sessions[replay_id]
    return True
