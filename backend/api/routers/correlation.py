"""
Correlation Router - 相关性分析 API 端点

架构：
    API Router
      ↓
    RuntimeBus (publish_command → CorrelationRuntime)
      ↓
    CorrelationRuntime
      ↓
    runtime_bus
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

from ..schemas.common import SuccessResponse

router = APIRouter()


class CorrelationAnalysisRequest(BaseModel):
    symbol: str = Field(default="BTCUSDT", description="币种")
    window: int = Field(default=30, description="分析窗口（天）")
    method: str = Field(default="pearson", description="相关性方法: pearson, spearman, kendall")


class SignalWeightUpdate(BaseModel):
    signal_id: str = Field(..., description="信号ID")
    weight: float = Field(..., description="权重 0.0-1.0", ge=0.0, le=1.0)
    reason: Optional[str] = Field(None, description="修改原因")


def _get_correlation_service():
    from application.services.correlation_service import get_correlation_service
    return get_correlation_service()


@router.get("/correlation/summary")
async def get_correlation_summary(
    symbol: str = Query(default="BTCUSDT", description="币种"),
) -> Dict[str, Any]:
    """获取相关性摘要"""
    service = _get_correlation_service()
    summary = await service.get_summary(symbol=symbol)
    return {
        "symbol": symbol,
        "summary": summary,
        "source": "correlation_runtime",
    }


@router.get("/correlation/matrix")
async def get_correlation_matrix(
    symbol: str = Query(default="BTCUSDT", description="币种"),
    window: int = Query(default=30, description="分析窗口（天）"),
) -> Dict[str, Any]:
    """获取相关性矩阵"""
    service = _get_correlation_service()
    matrix = await service.get_matrix(symbol=symbol, window=window)
    return {
        "symbol": symbol,
        "window": window,
        "matrix": matrix,
        "source": "correlation_runtime",
    }


@router.get("/correlation/signals/weights")
async def get_signal_weights(
    symbol: str = Query(default="BTCUSDT", description="币种"),
) -> Dict[str, Any]:
    """获取信号权重"""
    service = _get_correlation_service()
    weights = await service.get_signal_weights(symbol=symbol)
    return {
        "symbol": symbol,
        "weights": weights,
        "source": "correlation_runtime",
    }


@router.put("/correlation/signals/weights")
async def update_signal_weight(update: SignalWeightUpdate) -> Dict[str, Any]:
    """更新信号权重"""
    from runtime.bus.runtime_bus import get_runtime_bus

    bus = get_runtime_bus()
    await bus.publish_command(
        command="update_signal_weight",
        target="correlation_runtime",
        params={
            "signal_id": update.signal_id,
            "weight": update.weight,
            "reason": update.reason,
        },
        source="api.correlation",
    )

    service = _get_correlation_service()
    result = await service.update_signal_weight(
        signal_id=update.signal_id,
        weight=update.weight,
        reason=update.reason,
    )
    return {
        "success": True,
        "signal_id": update.signal_id,
        "weight": update.weight,
        "dispatch_via": "runtime_bus",
    }


@router.get("/correlation/analysis")
async def get_full_analysis(
    symbol: str = Query(default="BTCUSDT", description="币种"),
    window: int = Query(default=30, description="分析窗口（天）"),
) -> Dict[str, Any]:
    """获取完整分析结果"""
    service = _get_correlation_service()
    analysis = await service.get_full_analysis(symbol=symbol, window=window)
    return {
        "symbol": symbol,
        "window": window,
        "analysis": analysis,
        "source": "correlation_runtime",
    }


@router.post("/correlation/trigger")
async def trigger_analysis(
    request: CorrelationAnalysisRequest,
) -> Dict[str, Any]:
    """手动触发相关性分析 - 通过 RuntimeBus 调度到 CorrelationRuntime"""
    from runtime.bus.runtime_bus import get_runtime_bus

    bus = get_runtime_bus()
    await bus.publish_command(
        command="run_correlation_analysis",
        target="correlation_runtime",
        params={
            "symbol": request.symbol,
            "window": request.window,
            "method": request.method,
        },
        source="api.correlation",
    )

    service = _get_correlation_service()
    result = await service.run_analysis(
        symbol=request.symbol,
        window=request.window,
        method=request.method,
    )

    return {
        "success": True,
        "symbol": request.symbol,
        "result": result,
        "dispatch_via": "runtime_bus",
        "target": "correlation_runtime",
    }


@router.get("/correlation/history")
async def get_analysis_history(
    symbol: str = Query(default="BTCUSDT", description="币种"),
    limit: int = Query(default=10, description="返回数量"),
) -> Dict[str, Any]:
    """获取分析历史"""
    service = _get_correlation_service()
    history = await service.get_history(symbol=symbol, limit=limit)
    return {
        "symbol": symbol,
        "history": history,
    }
