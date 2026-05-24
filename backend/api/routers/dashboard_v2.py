from fastapi import APIRouter, Query
from typing import Dict, Any

from application.queries.analytics_queries import (
    get_dashboard_overview,
    get_dashboard_signals,
    get_dashboard_positions,
    get_dashboard_performance,
    get_dashboard_risk,
    get_dashboard_news,
    get_dashboard_social_posts,
    get_dashboard_high_frequency_data,
    get_dashboard_low_frequency_data,
    get_dashboard_market_data,
    get_dashboard_strategy_status,
    get_dashboard_correlation_summary,
    get_dashboard_factor_summary,
)

router = APIRouter()


@router.get("/dashboard/overview")
async def get_overview(symbol: str = Query(default="BTCUSDT")) -> Dict[str, Any]:
    return {"symbol": symbol, "overview": await get_dashboard_overview(symbol=symbol), "source": "projection_runtime"}


@router.get("/dashboard/signals")
async def get_signals(symbol: str = Query(default="BTCUSDT"), limit: int = Query(20)) -> Dict[str, Any]:
    return {"symbol": symbol, "signals": await get_dashboard_signals(symbol=symbol, limit=limit), "source": "projection_runtime"}


@router.get("/dashboard/positions")
async def get_positions(symbol: str = Query(default="BTCUSDT")) -> Dict[str, Any]:
    return {"symbol": symbol, "positions": await get_dashboard_positions(symbol=symbol), "source": "projection_runtime"}


@router.get("/dashboard/performance")
async def get_performance(symbol: str = Query(default="BTCUSDT"), period: str = Query("24h")) -> Dict[str, Any]:
    return {"symbol": symbol, "period": period, "performance": await get_dashboard_performance(symbol=symbol, period=period), "source": "projection_runtime"}


@router.get("/dashboard/risk")
async def get_risk(symbol: str = Query(default="BTCUSDT")) -> Dict[str, Any]:
    return {"symbol": symbol, "risk": await get_dashboard_risk(symbol=symbol), "source": "projection_runtime"}


@router.get("/dashboard/news")
async def get_news(
    symbol: str = Query(default="BTCUSDT"),
    page: int = Query(1),
    page_size: int = Query(10),
) -> Dict[str, Any]:
    return {
        "symbol": symbol,
        "news": await get_dashboard_news(symbol=symbol, page=page, page_size=page_size),
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
    return {
        "symbol": symbol,
        "posts": await get_dashboard_social_posts(symbol=symbol, page=page, page_size=page_size),
        "page": page,
        "page_size": page_size,
        "source": "projection_runtime",
    }


@router.get("/dashboard/high-frequency")
async def get_high_frequency_refresh(symbol: str = Query(default="BTCUSDT")) -> Dict[str, Any]:
    return {"symbol": symbol, "data": await get_dashboard_high_frequency_data(symbol=symbol), "source": "projection_runtime", "frequency": "high"}


@router.get("/dashboard/low-frequency")
async def get_low_frequency_refresh(symbol: str = Query(default="BTCUSDT")) -> Dict[str, Any]:
    return {"symbol": symbol, "data": await get_dashboard_low_frequency_data(symbol=symbol), "source": "projection_runtime", "frequency": "low"}


@router.get("/dashboard/market-data")
async def get_market_data(symbol: str = Query(default="BTCUSDT")) -> Dict[str, Any]:
    return {"symbol": symbol, "market_data": await get_dashboard_market_data(symbol=symbol), "source": "projection_runtime"}


@router.get("/dashboard/strategy-status")
async def get_strategy_status(symbol: str = Query(default="BTCUSDT")) -> Dict[str, Any]:
    return {"symbol": symbol, "strategy_status": await get_dashboard_strategy_status(symbol=symbol), "source": "projection_runtime"}


@router.get("/dashboard/correlation-summary")
async def get_correlation_summary(symbol: str = Query(default="BTCUSDT")) -> Dict[str, Any]:
    return {"symbol": symbol, "correlation_summary": await get_dashboard_correlation_summary(symbol=symbol), "source": "correlation_runtime"}


@router.get("/dashboard/factor-summary")
async def get_factor_summary(symbol: str = Query(default="BTCUSDT")) -> Dict[str, Any]:
    return {"symbol": symbol, "factor_summary": await get_dashboard_factor_summary(symbol=symbol), "source": "feature_runtime"}
