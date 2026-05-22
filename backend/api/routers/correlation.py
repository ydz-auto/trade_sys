"""
Correlation Router - 相关性分析 API 端点

架构：
    API Router (转发)
      ↓
    RuntimeBus.publish_command()
      ↓
    CorrelationRuntime (唯一 state source)
      ↓
    runtime_bus (state store)
"""
from fastapi import APIRouter, Query
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

router = APIRouter()


@router.get("/correlation/summary")
async def get_correlation_summary(
    symbol: str = Query(default="BTCUSDT", description="币种"),
) -> Dict[str, Any]:
    from application.services.correlation_service import get_correlation_service
    service = get_correlation_service()
    summary = await service.get_summary(symbol=symbol)
    return {"symbol": symbol, "summary": summary, "source": "correlation_runtime"}


@router.get("/correlation/matrix")
async def get_correlation_matrix(
    symbol: str = Query(default="BTCUSDT", description="币种"),
    window: int = Query(default=30, description="分析窗口（天）"),
) -> Dict[str, Any]:
    from application.services.correlation_service import get_correlation_service
    service = get_correlation_service()
    matrix = await service.get_matrix(symbol=symbol, window=window)
    return {"symbol": symbol, "window": window, "matrix": matrix, "source": "correlation_runtime"}


@router.get("/correlation/signals/weights")
async def get_signal_weights(
    symbol: str = Query(default="BTCUSDT", description="币种"),
) -> Dict[str, Any]:
    from application.services.correlation_service import get_correlation_service
    service = get_correlation_service()
    weights = await service.get_signal_weights(symbol=symbol)
    return {"symbol": symbol, "weights": weights, "source": "correlation_runtime"}


@router.put("/correlation/signals/weights")
async def update_signal_weight(
    signal_id: str = Query(...),
    weight: float = Query(..., ge=0.0, le=1.0),
    reason: Optional[str] = Query(None),
) -> Dict[str, Any]:
    from runtime.bus.runtime_bus import get_runtime_bus
    from application.services.correlation_service import get_correlation_service

    bus = get_runtime_bus()
    await bus.publish_command(
        command="update_signal_weight",
        target="correlation_runtime",
        params={"signal_id": signal_id, "weight": weight, "reason": reason},
        source="api.correlation",
    )

    service = get_correlation_service()
    await service.update_signal_weight(signal_id=signal_id, weight=weight, reason=reason)

    return {"success": True, "signal_id": signal_id, "weight": weight, "dispatch_via": "runtime_bus"}


@router.get("/correlation/analysis")
async def get_full_analysis(
    symbol: str = Query(default="BTCUSDT", description="币种"),
    window: int = Query(default=30, description="分析窗口（天）"),
) -> Dict[str, Any]:
    from application.services.correlation_service import get_correlation_service
    service = get_correlation_service()
    analysis = await service.get_full_analysis(symbol=symbol, window=window)
    return {"symbol": symbol, "window": window, "analysis": analysis, "source": "correlation_runtime"}


@router.post("/correlation/trigger")
async def trigger_analysis(
    symbol: str = Query(default="BTCUSDT", description="币种"),
    window: int = Query(default=30, description="分析窗口"),
    method: str = Query(default="pearson", description="相关性方法"),
) -> Dict[str, Any]:
    from runtime.bus.runtime_bus import get_runtime_bus
    from application.services.correlation_service import get_correlation_service

    bus = get_runtime_bus()
    await bus.publish_command(
        command="run_correlation_analysis",
        target="correlation_runtime",
        params={"symbol": symbol, "window": window, "method": method},
        source="api.correlation",
    )

    service = get_correlation_service()
    result = await service.run_analysis(symbol=symbol, window=window, method=method)

    return {
        "success": True,
        "symbol": symbol,
        "result": result,
        "dispatch_via": "runtime_bus",
        "target": "correlation_runtime",
    }


@router.get("/correlation/history")
async def get_analysis_history(
    symbol: str = Query(default="BTCUSDT", description="币种"),
    limit: int = Query(default=10, description="返回数量"),
) -> Dict[str, Any]:
    from application.services.correlation_service import get_correlation_service
    service = get_correlation_service()
    history = await service.get_history(symbol=symbol, limit=limit)
    return {"symbol": symbol, "history": history}
