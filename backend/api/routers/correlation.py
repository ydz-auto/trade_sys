"""
Correlation Router - 相关性分析 API 端点

架构（去 Facade 化）：
    API Router
      ↓
    RuntimeBus.publish_command()
      ↓
    CorrelationRuntime (唯一 state source)

不再使用已废弃的 application.services.correlation_service。
"""

from fastapi import APIRouter, Query
from typing import Optional, Dict, Any

router = APIRouter()


@router.get("/correlation/summary")
async def get_correlation_summary(
    symbol: str = Query(default="BTCUSDT", description="币种"),
) -> Dict[str, Any]:
    from application.queries.correlation import get_correlation_state

    state = await get_correlation_state()

    if state and state.get("summary"):
        return {"symbol": symbol, "summary": state["summary"], "source": "correlation_runtime"}

    return {"symbol": symbol, "summary": {}, "source": "correlation_runtime"}


@router.get("/correlation/matrix")
async def get_correlation_matrix(
    symbol: str = Query(default="BTCUSDT", description="币种"),
    window: int = Query(default=30, description="分析窗口（天）"),
) -> Dict[str, Any]:
    from application.queries.correlation import get_correlation_state

    state = await get_correlation_state()

    matrix_key = f"matrix_{symbol}_{window}"
    if state and state.get(matrix_key):
        return {"symbol": symbol, "window": window, "matrix": state[matrix_key], "source": "correlation_runtime"}

    return {"symbol": symbol, "window": window, "matrix": {}, "source": "correlation_runtime"}


@router.get("/correlation/signals/weights")
async def get_signal_weights(
    symbol: str = Query(default="BTCUSDT", description="币种"),
) -> Dict[str, Any]:
    from application.queries.correlation import get_correlation_state

    state = await get_correlation_state()

    weights = state.get("signal_weights", {}) if state else {}
    return {"symbol": symbol, "weights": weights, "source": "correlation_runtime"}


@router.put("/correlation/signals/weights")
async def update_signal_weight(
    signal_id: str = Query(...),
    weight: float = Query(..., ge=0.0, le=1.0),
    reason: Optional[str] = Query(None),
) -> Dict[str, Any]:
    from application.commands.bus_commands import publish_command

    await publish_command(
        command_type="update_signal_weight",
        data={"signal_id": signal_id, "weight": weight, "reason": reason},
        target="correlation_runtime",
    )

    return {
        "success": True,
        "signal_id": signal_id,
        "weight": weight,
        "dispatch_via": "runtime_bus",
        "target": "correlation_runtime"
    }


@router.get("/correlation/analysis")
async def get_full_analysis(
    symbol: str = Query(default="BTCUSDT", description="币种"),
    window: int = Query(default=30, description="分析窗口（天）"),
) -> Dict[str, Any]:
    from application.queries.correlation import get_correlation_state

    state = await get_correlation_state()

    analysis_key = f"analysis_{symbol}_{window}"
    if state and state.get(analysis_key):
        return {
            "symbol": symbol,
            "window": window,
            "analysis": state[analysis_key],
            "source": "correlation_runtime"
        }

    return {"symbol": symbol, "window": window, "analysis": {}, "source": "correlation_runtime"}


@router.post("/correlation/trigger")
async def trigger_analysis(
    symbol: str = Query(default="BTCUSDT", description="币种"),
    window: int = Query(default=30, description="分析窗口"),
    method: str = Query(default="pearson", description="相关性方法"),
) -> Dict[str, Any]:
    from application.commands.bus_commands import publish_command

    await publish_command(
        command_type="run_correlation_analysis",
        data={"symbol": symbol, "window": window, "method": method},
        target="correlation_runtime",
    )

    return {
        "success": True,
        "symbol": symbol,
        "window": window,
        "method": method,
        "dispatch_via": "runtime_bus",
        "target": "correlation_runtime",
    }


@router.get("/correlation/history")
async def get_analysis_history(
    symbol: str = Query(default="BTCUSDT", description="币种"),
    limit: int = Query(default=10, description="返回数量"),
) -> Dict[str, Any]:
    from application.queries.correlation import get_correlation_state

    state = await get_correlation_state()

    history_key = f"history_{symbol}"
    history = state.get(history_key, [])[-limit:] if state and state.get(history_key) else []

    return {"symbol": symbol, "history": history}
