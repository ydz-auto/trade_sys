"""
Feature Generation Router - 特征生成 API 端点
"""
from typing import List, Optional
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from domain.logging import get_logger

logger = get_logger("api.feature_generation")

router = APIRouter(prefix="/features", tags=["Feature Generation"])


class FeatureGenerationRequest(BaseModel):
    symbol: str
    years: List[int]
    intervals: List[str] = ["1m", "5m", "15m", "1h", "4h", "1d"]
    force_regenerate: bool = False


class FeatureGenerationResult(BaseModel):
    success: bool
    symbol: str
    interval: str
    records_generated: int
    storage_path: str
    clickhouse_stored: bool
    message: str
    timestamp: str


class FeatureGenerationResponse(BaseModel):
    success: bool
    symbol: str
    total_records: int
    results: List[FeatureGenerationResult]
    timestamp: str


class FeatureStatusResponse(BaseModel):
    symbol: str
    interval: str
    latest_timestamp: Optional[str]
    records_count: int
    storage_size_mb: float
    clickhouse_available: bool


@router.post("/generate", response_model=FeatureGenerationResponse)
async def generate_features(
    request: FeatureGenerationRequest
):
    """
    批量生成特征数据（多周期）
    
    从已下载的Trades数据提取特征，支持多周期聚合：
    - 1m: 1分钟特征（热数据，存SSD）
    - 5m: 5分钟特征
    - 15m: 15分钟特征
    - 1h: 1小时特征
    - 4h: 4小时特征
    - 1d: 日线特征
    
    存储到：
    - 本地数据湖 (Parquet + ZSTD)
    - ClickHouse (可选)
    """
    from api.services.feature_generation_service import generate_symbol_features
    
    try:
        logger.info(f"Starting feature generation for {request.symbol}")
        logger.info(f"Years: {request.years}, Intervals: {request.intervals}")
        
        results = await generate_symbol_features(
            symbol=request.symbol,
            years=request.years,
            intervals=request.intervals,
            force_regenerate=request.force_regenerate
        )
        
        total_records = sum(r.get("records_generated", 0) for r in results)
        
        return FeatureGenerationResponse(
            success=True,
            symbol=request.symbol,
            total_records=total_records,
            results=[
                FeatureGenerationResult(**r) for r in results
            ],
            timestamp=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Feature generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{symbol}", response_model=List[FeatureStatusResponse])
async def get_feature_status(
    symbol: str,
    interval: Optional[str] = Query(None, description="时间周期，如 1m, 5m, 15m, 1h")
):
    """
    获取特征数据状态
    
    返回各时间周期的特征数据统计信息
    """
    from api.services.feature_generation_service import get_feature_status
    
    try:
        return await get_feature_status(symbol, interval)
    except Exception as e:
        logger.error(f"Failed to get feature status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/intervals")
async def get_available_intervals():
    """
    获取支持的时间周期列表
    """
    return {
        "intervals": [
            {"name": "1m", "description": "1分钟特征", "storage": "SSD热存储"},
            {"name": "5m", "description": "5分钟特征", "storage": "HDD"},
            {"name": "15m", "description": "15分钟特征", "storage": "HDD"},
            {"name": "1h", "description": "1小时特征", "storage": "HDD"},
            {"name": "4h", "description": "4小时特征", "storage": "HDD"},
            {"name": "1d", "description": "日线特征", "storage": "HDD"}
        ],
        "total": 6
    }


@router.delete("/cache/{symbol}")
async def clear_feature_cache(
    symbol: str,
    interval: Optional[str] = Query(None, description="时间周期")
):
    """
    清除特征缓存
    
    用于强制重新生成特征数据
    """
    from api.services.feature_generation_service import clear_feature_cache
    
    try:
        cleared = await clear_feature_cache(symbol, interval)
        return {
            "success": True,
            "symbol": symbol,
            "interval": interval or "all",
            "cleared_files": cleared,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to clear feature cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))
