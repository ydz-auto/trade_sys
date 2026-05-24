"""Feature Matrix Router - 特征矩阵 API 端点

架构：
    API Router (转发)
      ↓
    Application Queries/Commands
      ↓
    RuntimeBus / FeatureRuntime / ReplayRuntime
"""
from fastapi import APIRouter, Query
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from application.queries.feature import (
    get_feature_metadata,
    get_feature_matrix,
    get_feature_categories,
    update_feature_weight,
    trigger_feature_backtest,
    get_feature_correlation,
    get_feature_importance,
)
from ..schemas.common import SuccessResponse

router = APIRouter()


class FeatureWeightUpdate(BaseModel):
    feature_name: str
    weight: float = Field(..., ge=0.0, le=1.0)
    reason: Optional[str] = None


class BatchWeightUpdate(BaseModel):
    updates: List[FeatureWeightUpdate]


@router.get("/feature-matrix/metadata")
async def get_feature_metadata_endpoint(
    symbol: str = Query(default="BTCUSDT"),
    category: Optional[str] = Query(None),
):
    metadata = await get_feature_metadata(symbol=symbol, category=category)
    return {"symbol": symbol, "metadata": metadata, "runtime_enabled": True}


@router.get("/feature-matrix")
async def get_feature_matrix_endpoint(
    symbol: str = Query(default="BTCUSDT"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(100),
):
    matrix = await get_feature_matrix(symbol=symbol, start_date=start_date, end_date=end_date, limit=limit)
    return {"symbol": symbol, "matrix": matrix, "runtime_enabled": True}


@router.get("/feature-matrix/categories")
async def get_feature_categories_endpoint(symbol: str = Query(default="BTCUSDT")):
    categories = await get_feature_categories(symbol=symbol)
    return {"symbol": symbol, "categories": categories}


@router.put("/feature-matrix/weights")
async def update_feature_weights(update: FeatureWeightUpdate):
    result = await update_feature_weight(feature_name=update.feature_name, weight=update.weight, reason=update.reason)
    return SuccessResponse(success=True, message=f"Weight updated for {update.feature_name}", data=result)


@router.put("/feature-matrix/weights/batch")
async def batch_update_weights(update: BatchWeightUpdate):
    results = [await update_feature_weight(u.feature_name, u.weight, u.reason) for u in update.updates]
    return SuccessResponse(success=True, message=f"Updated {len(results)} feature weights", data=results)


@router.post("/feature-matrix/backtest/trigger")
async def trigger_backtest(symbol: str = Query(default="BTCUSDT")):
    result = await trigger_feature_backtest(symbol)
    return SuccessResponse(
        success=True,
        message=f"Backtest triggered for {symbol} via RuntimeBus",
        data={**result, "dispatch_via": "runtime_bus"},
    )


@router.get("/feature-matrix/correlation")
async def get_feature_correlation_endpoint(
    symbol: str = Query(default="BTCUSDT"),
    features: Optional[str] = Query(None),
):
    feature_list = features.split(",") if features else None
    return await get_feature_correlation(symbol=symbol, features=feature_list)


@router.get("/feature-matrix/importance")
async def get_feature_importance_endpoint(symbol: str = Query(default="BTCUSDT"), top_n: int = Query(20)):
    return await get_feature_importance(symbol=symbol, top_n=top_n)
