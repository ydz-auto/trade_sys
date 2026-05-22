"""
Feature Matrix Router - 特征矩阵 API 端点

架构：
    API Router
      ↓
    FeatureMatrixService (读取)
    RuntimeBus (回测命令 → ReplayRuntime)
"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from ..services.feature_matrix import get_feature_matrix_service
from ..schemas.common import SuccessResponse

router = APIRouter()


class FeatureWeightUpdate(BaseModel):
    feature_name: str = Field(..., description="特征名称")
    weight: float = Field(..., description="权重 0.0-1.0", ge=0.0, le=1.0)
    reason: Optional[str] = Field(None, description="修改原因")


class BatchWeightUpdate(BaseModel):
    updates: List[FeatureWeightUpdate] = Field(..., description="批量权重更新")


def get_service():
    return get_feature_matrix_service()


@router.get("/feature-matrix/metadata")
async def get_feature_metadata(
    symbol: str = Query(default="BTCUSDT", description="币种"),
    category: Optional[str] = Query(None, description="特征分类过滤"),
):
    """获取特征元数据"""
    service = get_service()
    metadata = await service.get_metadata(symbol=symbol, category=category)
    return {
        "symbol": symbol,
        "metadata": metadata,
        "runtime_enabled": True,
    }


@router.get("/feature-matrix")
async def get_feature_matrix(
    symbol: str = Query(default="BTCUSDT", description="币种"),
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    limit: int = Query(default=100, description="返回数量"),
):
    """获取特征矩阵"""
    service = get_service()
    matrix = await service.get_matrix(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )
    return {
        "symbol": symbol,
        "matrix": matrix,
        "runtime_enabled": True,
    }


@router.get("/feature-matrix/categories")
async def get_feature_categories(
    symbol: str = Query(default="BTCUSDT", description="币种"),
):
    """按分类获取特征"""
    service = get_service()
    categories = await service.get_categories(symbol=symbol)
    return {
        "symbol": symbol,
        "categories": categories,
    }


@router.put("/feature-matrix/weights")
async def update_feature_weights(update: FeatureWeightUpdate):
    """更新特征权重"""
    service = get_service()
    result = await service.update_weight(
        feature_name=update.feature_name,
        weight=update.weight,
        reason=update.reason,
    )
    return SuccessResponse(
        success=True,
        message=f"Weight updated for {update.feature_name}",
        data=result,
    )


@router.put("/feature-matrix/weights/batch")
async def batch_update_weights(update: BatchWeightUpdate):
    """批量更新特征权重"""
    service = get_service()
    results = []
    for u in update.updates:
        result = await service.update_weight(
            feature_name=u.feature_name,
            weight=u.weight,
            reason=u.reason,
        )
        results.append(result)
    return SuccessResponse(
        success=True,
        message=f"Updated {len(results)} feature weights",
        data=results,
    )


@router.post("/feature-matrix/backtest/trigger")
async def trigger_backtest(
    symbol: str = Query(default="BTCUSDT", description="币种"),
):
    """触发回测 - 通过 RuntimeBus 调度到 ReplayRuntime"""
    from runtime.bus.runtime_bus import get_runtime_bus

    bus = get_runtime_bus()
    await bus.publish_command(
        command="run_backtest",
        target="backtest_service",
        params={
            "symbol": symbol,
            "source": "feature_matrix",
        },
        source="api.feature_matrix",
    )

    service = get_service()
    result = await service.trigger_backtest(symbol)

    return SuccessResponse(
        success=True,
        message=f"Backtest triggered for {symbol} via RuntimeBus",
        data={
            **result,
            "dispatch_via": "runtime_bus",
        },
    )


@router.get("/feature-matrix/correlation")
async def get_feature_correlation(
    symbol: str = Query(default="BTCUSDT", description="币种"),
    features: Optional[str] = Query(None, description="特征列表（逗号分隔）"),
):
    """获取特征相关性"""
    service = get_service()
    feature_list = features.split(",") if features else None
    correlation = await service.get_correlation(symbol=symbol, features=feature_list)
    return {
        "symbol": symbol,
        "correlation": correlation,
    }


@router.get("/feature-matrix/importance")
async def get_feature_importance(
    symbol: str = Query(default="BTCUSDT", description="币种"),
    top_n: int = Query(default=20, description="返回前N个"),
):
    """获取特征重要性"""
    service = get_service()
    importance = await service.get_importance(symbol=symbol, top_n=top_n)
    return {
        "symbol": symbol,
        "importance": importance,
    }
