"""
Unified Feature API (Converged Version) - 统一特征服务API

收敛版架构：
- GET /feature/matrix/history: 获取历史特征矩阵
- GET /feature/matrix/realtime: 获取实时特征矩阵
- GET /feature/group/{category}: 获取单特征组
- GET /feature/snapshot: 获取特征快照
- POST /feature/materialize: 物化历史特征
- GET /feature/available: 获取可用特征列表
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel

from domain.logging import get_logger
from application.queries.domain_queries import (
    get_historical_feature_matrix,
    get_available_features,
    get_schema_registry,
    get_historical_feature_materializer,
    get_materializer_feature_category_enum,
)

logger = get_logger("api.feature")

router = APIRouter(prefix="/feature", tags=["Unified Feature Service"])

DATA_LAKE_ROOT = Path(r"e:\00_crypto\00_code\backend\data_lake")


class MaterializeRequest(BaseModel):
    symbol: str
    interval_ms: int = 60000
    force: bool = False
    start_ts: Optional[int] = None
    end_ts: Optional[int] = None


class FeatureMatrixResponse(BaseModel):
    symbol: str
    interval_ms: int
    timestamps: List[int]
    feature_names: List[str]
    feature_vector: Dict[str, List[float]]
    shape: tuple
    metadata: Dict[str, Any]
    generated_at: str


@router.get("/matrix/history", response_model=FeatureMatrixResponse)
async def get_historical_matrix(
    symbol: str = Query(..., description="交易对"),
    interval_ms: int = Query(60000, description="时间间隔(ms)"),
    limit: int = Query(100, description="返回数量"),
    start_ts: Optional[int] = Query(None, description="开始时间戳(ms)"),
    end_ts: Optional[int] = Query(None, description="结束时间戳(ms)"),
    force: bool = Query(False, description="是否强制重新生成")
):
    """获取历史特征矩阵"""
    try:
        logger.info(f"Fetching historical matrix for {symbol}")
        
        matrix = get_historical_feature_matrix(
            symbol=symbol,
            interval_ms=interval_ms,
            limit=limit,
            start_ts=start_ts,
            end_ts=end_ts,
            force=force
        )
        
        return FeatureMatrixResponse(
            symbol=matrix.symbol,
            interval_ms=matrix.interval_ms,
            timestamps=matrix.timestamps,
            feature_names=list(matrix.feature_vector.keys()),
            feature_vector=matrix.feature_vector,
            shape=matrix.shape,
            metadata=matrix.metadata,
            generated_at=datetime.now().isoformat()
        )
    
    except Exception as e:
        logger.error(f"Failed to get historical matrix: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/group/{category}")
async def get_feature_group(
    category: str,
    symbol: str = Query(..., description="交易对"),
    interval_ms: int = Query(60000, description="时间间隔(ms)"),
    limit: int = Query(100, description="返回数量")
):
    """获取单特征组数据"""
    try:
        FeatureCategory = get_materializer_feature_category_enum()
        category_enum = FeatureCategory(category.lower())
        
        registry = get_schema_registry()
        group_schemas = registry.get_schemas_by_category(category_enum)
        group_feature_names = [s.name for s in group_schemas]
        
        # 获取完整矩阵后筛选
        matrix = get_historical_feature_matrix(
            symbol=symbol,
            interval_ms=interval_ms,
            limit=limit
        )
        
        group_vector = {
            name: values
            for name, values in matrix.feature_vector.items()
            if name in group_feature_names
        }
        
        return {
            "category": category,
            "symbol": symbol,
            "feature_names": list(group_vector.keys()),
            "timestamps": matrix.timestamps,
            "feature_vector": group_vector
        }
    
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid category: {category}")
    except Exception as e:
        logger.error(f"Failed to get feature group: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/snapshot")
async def get_feature_snapshot(
    symbol: str = Query(..., description="交易对"),
    interval_ms: int = Query(60000, description="时间间隔(ms)")
):
    """获取最新特征快照"""
    try:
        matrix = get_historical_feature_matrix(
            symbol=symbol,
            interval_ms=interval_ms,
            limit=1
        )
        
        if len(matrix.timestamps) == 0:
            raise HTTPException(status_code=404, detail="No data available")
        
        latest_ts = matrix.timestamps[-1]
        latest_vector = {
            name: values[-1]
            for name, values in matrix.feature_vector.items()
        }
        
        return {
            "symbol": symbol,
            "timestamp": latest_ts,
            "datetime": datetime.fromtimestamp(latest_ts / 1000).isoformat(),
            "feature_vector": latest_vector
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get snapshot: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/materialize")
async def materialize_features(request: MaterializeRequest):
    """物化历史特征矩阵"""
    try:
        logger.info(f"Materializing features for {request.symbol}")
        
        materializer = get_historical_feature_materializer(DATA_LAKE_ROOT)
        matrix = materializer.materialize_symbol(
            symbol=request.symbol,
            interval_ms=request.interval_ms,
            start_ts=request.start_ts,
            end_ts=request.end_ts,
            force=request.force
        )
        
        return {
            "success": True,
            "symbol": request.symbol,
            "shape": matrix.shape,
            "message": f"Materialized {matrix.shape[0]} timestamps with {matrix.shape[1]} features"
        }
    
    except Exception as e:
        logger.error(f"Failed to materialize: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/available")
async def get_available_features_endpoint():
    """获取可用特征列表（收敛版6大组）"""
    try:
        features = get_available_features()
        
        # 按分类分组
        grouped: Dict[str, List[Dict]] = {}
        for f in features:
            cat = f["category"]
            if cat not in grouped:
                grouped[cat] = []
            grouped[cat].append(f)
        
        return {
            "total_features": len(features),
            "categories": list(grouped.keys()),
            "features_by_category": grouped,
            "required_features": [f["name"] for f in features if f["is_required"]]
        }
    
    except Exception as e:
        logger.error(f"Failed to get available features: {e}")
        raise HTTPException(status_code=500, detail=str(e))

