"""
Dashboard V2 Router - 独立接口

架构：
    API Router
      ↓
    DashboardService (读取)
      ↓
    ProjectionReader (从 ProjectionRuntime 写入的 Redis 状态读取)
      ↓
    ProjectionRuntime (写入方，通过 RuntimeBus)

注意：Dashboard 是 CQRS 的读取端，通过 ProjectionReader 读取状态，
不直接操作 Redis。写入操作通过 RuntimeBus 调度到对应 Runtime。
"""
from fastapi import APIRouter, Query
from typing import Optional, Dict, Any, List

from ..services.dashboard import get_dashboard_service

router = APIRouter()


def _get_service():
    return get_dashboard_service()


@router.get("/dashboard/overview")
async def get_overview(
    symbol: str = Query(default="BTCUSDT", description="币种"),
) -> Dict[str, Any]:
    """获取概览数据"""
    service = _get_service()
    overview = await service.get_overview(symbol=symbol)
    return {
        "symbol": symbol,
        "overview": overview,
        "source": "projection_runtime",
    }


@router.get("/dashboard/signals")
async def get_signals(
    symbol: str = Query(default="BTCUSDT", description="币种"),
    limit: int = Query(default=20, description="返回数量"),
) -> Dict[str, Any]:
    """获取信号列表"""
    service = _get_service()
    signals = await service.get_signals(symbol=symbol, limit=limit)
    return {
        "symbol": symbol,
        "signals": signals,
        "source": "projection_runtime",
    }


@router.get("/dashboard/positions")
async def get_positions(
    symbol: str = Query(default="BTCUSDT", description="币种"),
) -> Dict[str, Any]:
    """获取持仓信息"""
    service = _get_service()
    positions = await service.get_positions(symbol=symbol)
    return {
        "symbol": symbol,
        "positions": positions,
        "source": "projection_runtime",
    }


@router.get("/dashboard/performance")
async def get_performance(
    symbol: str = Query(default="BTCUSDT", description="币种"),
    period: str = Query(default="24h", description="时间周期: 1h, 24h, 7d, 30d"),
) -> Dict[str, Any]:
    """获取绩效数据"""
    service = _get_service()
    performance = await service.get_performance(symbol=symbol, period=period)
    return {
        "symbol": symbol,
        "period": period,
        "performance": performance,
        "source": "projection_runtime",
    }


@router.get("/dashboard/risk")
async def get_risk(
    symbol: str = Query(default="BTCUSDT", description="币种"),
) -> Dict[str, Any]:
    """获取风险数据"""
    service = _get_service()
    risk = await service.get_risk(symbol=symbol)
    return {
        "symbol": symbol,
        "risk": risk,
        "source": "projection_runtime",
    }


@router.get("/dashboard/news")
async def get_news(
    symbol: str = Query(default="BTCUSDT", description="币种"),
    page: int = Query(default=1, description="页码"),
    page_size: int = Query(default=10, description="每页数量"),
) -> Dict[str, Any]:
    """获取新闻（分页）"""
    service = _get_service()
    news = await service.get_news(
        symbol=symbol,
        page=page,
        page_size=page_size,
    )
    return {
        "symbol": symbol,
        "news": news,
        "page": page,
        "page_size": page_size,
        "source": "projection_runtime",
    }


@router.get("/dashboard/social")
async def get_social_posts(
    symbol: str = Query(default="BTCUSDT", description="币种"),
    page: int = Query(default=1, description="页码"),
    page_size: int = Query(default=10, description="每页数量"),
) -> Dict[str, Any]:
    """获取社交帖子（分页）"""
    service = _get_service()
    posts = await service.get_social_posts(
        symbol=symbol,
        page=page,
        page_size=page_size,
    )
    return {
        "symbol": symbol,
        "posts": posts,
        "page": page,
        "page_size": page_size,
        "source": "projection_runtime",
    }


@router.get("/dashboard/high-frequency")
async def get_high_frequency_refresh(
    symbol: str = Query(default="BTCUSDT", description="币种"),
) -> Dict[str, Any]:
    """高频刷新数据（价格、持仓、PnL）"""
    service = _get_service()
    data = await service.get_high_frequency_data(symbol=symbol)
    return {
        "symbol": symbol,
        "data": data,
        "source": "projection_runtime",
        "frequency": "high",
    }


@router.get("/dashboard/low-frequency")
async def get_low_frequency_refresh(
    symbol: str = Query(default="BTCUSDT", description="币种"),
) -> Dict[str, Any]:
    """低频刷新数据（信号、风险、绩效）"""
    service = _get_service()
    data = await service.get_low_frequency_data(symbol=symbol)
    return {
        "symbol": symbol,
        "data": data,
        "source": "projection_runtime",
        "frequency": "low",
    }


@router.get("/dashboard/market-data")
async def get_market_data(
    symbol: str = Query(default="BTCUSDT", description="币种"),
) -> Dict[str, Any]:
    """获取市场数据"""
    service = _get_service()
    market_data = await service.get_market_data(symbol=symbol)
    return {
        "symbol": symbol,
        "market_data": market_data,
        "source": "projection_runtime",
    }


@router.get("/dashboard/strategy-status")
async def get_strategy_status(
    symbol: str = Query(default="BTCUSDT", description="币种"),
) -> Dict[str, Any]:
    """获取策略状态"""
    service = _get_service()
    status = await service.get_strategy_status(symbol=symbol)
    return {
        "symbol": symbol,
        "strategy_status": status,
        "source": "projection_runtime",
    }


@router.get("/dashboard/correlation-summary")
async def get_correlation_summary(
    symbol: str = Query(default="BTCUSDT", description="币种"),
) -> Dict[str, Any]:
    """获取相关性摘要"""
    service = _get_service()
    summary = await service.get_correlation_summary(symbol=symbol)
    return {
        "symbol": symbol,
        "correlation_summary": summary,
        "source": "correlation_runtime",
    }


@router.get("/dashboard/factor-summary")
async def get_factor_summary(
    symbol: str = Query(default="BTCUSDT", description="币种"),
) -> Dict[str, Any]:
    """获取因子摘要"""
    service = _get_service()
    summary = await service.get_factor_summary(symbol=symbol)
    return {
        "symbol": symbol,
        "factor_summary": summary,
        "source": "feature_runtime",
    }
