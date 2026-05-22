"""
Dashboard V2 Router - 独立接口

架构：
    API Router (只读)
      ↓
    DashboardService (读取聚合)
      ↓
    ProjectionReader (CQRS 读端)
      ↓
    ProjectionRuntime (写入端)
"""
from fastapi import APIRouter, Query
from typing import Optional, Dict, Any

from ..services.dashboard import get_dashboard_service

router = APIRouter()


@router.get("/dashboard/overview")
async def get_overview(symbol: str = Query(default="BTCUSDT")) -> Dict[str, Any]:
    service = get_dashboard_service()
    return {"symbol": symbol, "overview": await service.get_overview(symbol=symbol), "source": "projection_runtime"}


@router.get("/dashboard/signals")
async def get_signals(symbol: str = Query(default="BTCUSDT"), limit: int = Query(20)) -> Dict[str, Any]:
    service = get_dashboard_service()
    return {"symbol": symbol, "signals": await service.get_signals(symbol=symbol, limit=limit), "source": "projection_runtime"}


@router.get("/dashboard/positions")
async def get_positions(symbol: str = Query(default="BTCUSDT")) -> Dict[str, Any]:
    service = get_dashboard_service()
    return {"symbol": symbol, "positions": await service.get_positions(symbol=symbol), "source": "projection_runtime"}


@router.get("/dashboard/performance")
async def get_performance(symbol: str = Query(default="BTCUSDT"), period: str = Query("24h")) -> Dict[str, Any]:
    service = get_dashboard_service()
    return {"symbol": symbol, "period": period, "performance": await service.get_performance(symbol=symbol, period=period), "source": "projection_runtime"}


@router.get("/dashboard/risk")
async def get_risk(symbol: str = Query(default="BTCUSDT")) -> Dict[str, Any]:
    service = get_dashboard_service()
    return {"symbol": symbol, "risk": await service.get_risk(symbol=symbol), "source": "projection_runtime"}


@router.get("/dashboard/news")
async def get_news(
    symbol: str = Query(default="BTCUSDT"),
    page: int = Query(1),
    page_size: int = Query(10),
) -> Dict[str, Any]:
    service = get_dashboard_service()
    return {
        "symbol": symbol,
        "news": await service.get_news(symbol=symbol, page=page, page_size=page_size),
        "page": page,
        "page_size": page_size,
        "source": "projection_runtime",
    }


@router.get("/dashboard/social")
async def get_social_posts(
    symbol: str = Query(default="BTCUSDT"),
    page: int = Query(1),
    page_size: int = Query(10),
) -> Dict[str, Any]:
    service = get_dashboard_service()
    return {
        "symbol": symbol,
        "posts": await service.get_social_posts(symbol=symbol, page=page, page_size=page_size),
        "page": page,
        "page_size": page_size,
        "source": "projection_runtime",
    }


@router.get("/dashboard/high-frequency")
async def get_high_frequency_refresh(symbol: str = Query(default="BTCUSDT")) -> Dict[str, Any]:
    service = get_dashboard_service()
    return {"symbol": symbol, "data": await service.get_high_frequency_data(symbol=symbol), "source": "projection_runtime", "frequency": "high"}


@router.get("/dashboard/low-frequency")
async def get_low_frequency_refresh(symbol: str = Query(default="BTCUSDT")) -> Dict[str, Any]:
    service = get_dashboard_service()
    return {"symbol": symbol, "data": await service.get_low_frequency_data(symbol=symbol), "source": "projection_runtime", "frequency": "low"}


@router.get("/dashboard/market-data")
async def get_market_data(symbol: str = Query(default="BTCUSDT")) -> Dict[str, Any]:
    service = get_dashboard_service()
    return {"symbol": symbol, "market_data": await service.get_market_data(symbol=symbol), "source": "projection_runtime"}


@router.get("/dashboard/strategy-status")
async def get_strategy_status(symbol: str = Query(default="BTCUSDT")) -> Dict[str, Any]:
    service = get_dashboard_service()
    return {"symbol": symbol, "strategy_status": await service.get_strategy_status(symbol=symbol), "source": "projection_runtime"}


@router.get("/dashboard/correlation-summary")
async def get_correlation_summary(symbol: str = Query(default="BTCUSDT")) -> Dict[str, Any]:
    service = get_dashboard_service()
    return {"symbol": symbol, "correlation_summary": await service.get_correlation_summary(symbol=symbol), "source": "correlation_runtime"}


@router.get("/dashboard/factor-summary")
async def get_factor_summary(symbol: str = Query(default="BTCUSDT")) -> Dict[str, Any]:
    service = get_dashboard_service()
    return {"symbol": symbol, "factor_summary": await service.get_factor_summary(symbol=symbol), "source": "feature_runtime"}
