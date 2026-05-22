"""
Feature Matrix Router - 特征矩阵 API 端点

架构：
    API Router (只读 + 刷新触发)
      ↓
    FeatureMatrixService (读取聚合)
      ↓
    RuntimeBus.publish_command() (回测触发)
      ↓
    FeatureRuntime / ReplayRuntime
"""
from fastapi import APIRouter, Query
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from ..services.feature_matrix import get_feature_matrix_service
from ..schemas.common import SuccessResponse

router = APIRouter()


class FeatureWeightUpdate(BaseModel):
    feature_name: str
    weight: float = Field(..., ge=0.0, le=1.0)
    reason: Optional[str] = None


class BatchWeightUpdate(BaseModel):
    updates: List[FeatureWeightUpdate]


@router.get("/feature-matrix/metadata")
async def get_feature_metadata(
    symbol: str = Query(default="BTCUSDT"),
    category: Optional[str] = Query(None),
):
    service = get_feature_matrix_service()
    return {"symbol": symbol, "metadata": await service.get_metadata(symbol=symbol, category=category), "runtime_enabled": True}


@router.get("/feature-matrix")
async def get_feature_matrix(
    symbol: str = Query(default="BTCUSDT"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(100),
):
    service = get_feature_matrix_service()
    return {"symbol": symbol, "matrix": await service.get_matrix(symbol=symbol, start_date=start_date, end_date=end_date, limit=limit), "runtime_enabled": True}


@router.get("/feature-matrix/categories")
async def get_feature_categories(symbol: str = Query(default="BTCUSDT")):
    service = get_feature_matrix_service()
    return {"symbol": symbol, "categories": await service.get_categories(symbol=symbol)}


@router.put("/feature-matrix/weights")
async def update_feature_weights(update: FeatureWeightUpdate):
    service = get_feature_matrix_service()
    result = await service.update_weight(feature_name=update.feature_name, weight=update.weight, reason=update.reason)
    return SuccessResponse(success=True, message=f"Weight updated for {update.feature_name}", data=result)


@router.put("/feature-matrix/weights/batch")
async def batch_update_weights(update: BatchWeightUpdate):
    service = get_feature_matrix_service()
    results = [await service.update_weight(u.feature_name, u.weight, u.reason) for u in update.updates]
    return SuccessResponse(success=True, message=f"Updated {len(results)} feature weights", data=results)


@router.post("/feature-matrix/backtest/trigger")
async def trigger_backtest(symbol: str = Query(default="BTCUSDT")):
    from runtime.bus.runtime_bus import get_runtime_bus

    bus = get_runtime_bus()
    await bus.publish_command(
        command="run_backtest",
        target="replay_runtime",
        params={"symbol": symbol, "source": "feature_matrix"},
        source="api.feature_matrix",
    )

    service = get_feature_matrix_service()
    result = await service.trigger_backtest(symbol)
    return SuccessResponse(
        success=True,
        message=f"Backtest triggered for {symbol} via RuntimeBus",
        data={**result, "dispatch_via": "runtime_bus"},
    )


@router.get("/feature-matrix/correlation")
async def get_feature_correlation(
    symbol: str = Query(default="BTCUSDT"),
    features: Optional[str] = Query(None),
):
    service = get_feature_matrix_service()
    feature_list = features.split(",") if features else None
    return {"symbol": symbol, "correlation": await service.get_correlation(symbol=symbol, features=feature_list)}


@router.get("/feature-matrix/importance")
async def get_feature_importance(symbol: str = Query(default="BTCUSDT"), top_n: int = Query(20)):
    service = get_feature_matrix_service()
    return {"symbol": symbol, "importance": await service.get_importance(symbol=symbol, top_n=top_n)}
