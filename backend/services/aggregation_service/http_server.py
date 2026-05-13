"""
Aggregation Service HTTP Server
提供健康检查、API 端点
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import FastAPI, Response
from pydantic import BaseModel

from services.aggregation_service import get_aggregation_service, AggregationService
from services.aggregation_service.state.state_manager import get_window_state_manager
from infrastructure.logging import get_logger

logger = get_logger("aggregation_service.http")

app = FastAPI(title="Aggregation Service", version="1.0.0")


class HealthResponse(BaseModel):
    status: str
    service: str
    stats: Dict[str, Any]
    windows_count: int
    timestamp: str


_service: AggregationService = None


@app.on_event("startup")
async def startup_event():
    """启动时初始化"""
    global _service
    
    print("=" * 60)
    print("Starting Aggregation Service HTTP Server")
    print("=" * 60)
    
    _service = await get_aggregation_service()
    print("✅ Aggregation Service initialized")
    print("=" * 60)


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """健康检查端点"""
    state_manager = get_window_state_manager()
    windows_count = len(state_manager.windows)
    
    return HealthResponse(
        status="ok" if _service else "degraded",
        service="aggregation_service",
        stats=_service.stats if _service else {},
        windows_count=windows_count,
        timestamp=datetime.utcnow().isoformat() + "Z",
    )


@app.get("/stats")
async def get_stats():
    """获取统计信息"""
    if not _service:
        return {"error": "Service not initialized"}
    
    return _service.stats


@app.get("/windows")
async def get_windows():
    """获取所有聚合窗口状态"""
    state_manager = get_window_state_manager()
    return state_manager.to_dict()


if __name__ == "__main__":
    import uvicorn
    
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8002"))
    
    uvicorn.run(app, host=host, port=port)
