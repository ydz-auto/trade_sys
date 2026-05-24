"""Feature Generation Router - 特征生成 API 端点

架构：
    API Router (转发)
      ↓
    Application Commands
      ↓
    FeatureRuntime / DataPipeline
"""
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

import logging

logger = logging.getLogger(__name__)

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
async def generate_features(request: FeatureGenerationRequest):
    from application.commands.data_commands import trigger_feature_generation

    try:
        logger.info(f"Starting feature generation for {request.symbol}")

        results = await trigger_feature_generation(
            symbol=request.symbol,
            years=request.years,
            intervals=request.intervals,
            force_regenerate=request.force_regenerate,
        )

        total_records = sum(r.get("records_generated", 0) for r in results)

        return FeatureGenerationResponse(
            success=True,
            symbol=request.symbol,
            total_records=total_records,
            results=[FeatureGenerationResult(**r) for r in results],
            timestamp=datetime.utcnow().isoformat(),
        )

    except Exception as e:
        logger.error(f"Feature generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{symbol}", response_model=List[FeatureStatusResponse])
async def get_feature_status(
    symbol: str,
    interval: Optional[str] = Query(None, description="Time interval"),
):
    from application.queries.feature import get_feature_state

    try:
        state = await get_feature_state()
        return state.get("status", [])
    except Exception as e:
        logger.error(f"Failed to get feature status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/intervals")
async def get_available_intervals():
    return {
        "intervals": [
            {"name": "1m", "description": "1 min", "storage": "SSD"},
            {"name": "5m", "description": "5 min", "storage": "HDD"},
            {"name": "15m", "description": "15 min", "storage": "HDD"},
            {"name": "1h", "description": "1 hour", "storage": "HDD"},
            {"name": "4h", "description": "4 hour", "storage": "HDD"},
            {"name": "1d", "description": "Daily", "storage": "HDD"},
        ],
        "total": 6,
    }


@router.delete("/cache/{symbol}")
async def clear_feature_cache(
    symbol: str,
    interval: Optional[str] = Query(None, description="Time interval"),
):
    from application.commands.bus_commands import publish_command

    try:
        await publish_command(
            command_type="clear_feature_cache",
            data={"symbol": symbol, "interval": interval},
            target="feature_runtime",
        )
        return {
            "success": True,
            "symbol": symbol,
            "interval": interval or "all",
            "dispatch_via": "runtime_bus",
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to clear feature cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))
