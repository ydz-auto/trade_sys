"""
Refresh Router - 数据刷新 API 端点

架构：
    API Router
      ↓
    RuntimeBus (publish_command → 对应 Runtime)
      ↓
    各 Runtime 处理刷新
      ↓
    runtime_bus

注意：所有刷新命令通过 RuntimeBus 调度到对应 Runtime，
不再直接使用 Redis pub/sub。
"""
from fastapi import APIRouter, Query
from typing import Dict, Any

from ..schemas.common import SuccessResponse

router = APIRouter()


async def _dispatch_refresh(command: str, target: str, params: dict):
    from runtime.bus.runtime_bus import get_runtime_bus

    bus = get_runtime_bus()
    await bus.publish_command(
        command=command,
        target=target,
        params=params,
        source="api.refresh",
    )


@router.post("/refresh/price")
async def refresh_price(
    symbol: str = Query(default="BTCUSDT", description="币种"),
) -> Dict[str, Any]:
    """刷新价格数据 - 通过 RuntimeBus 调度"""
    await _dispatch_refresh(
        command="refresh_price",
        target="data_runtime",
        params={"symbol": symbol},
    )

    return {
        "success": True,
        "symbol": symbol,
        "message": "Price refresh dispatched via RuntimeBus",
        "dispatch_via": "runtime_bus",
        "target": "data_runtime",
    }


@router.post("/refresh/signals")
async def refresh_signals(
    symbol: str = Query(default="BTCUSDT", description="币种"),
) -> Dict[str, Any]:
    """刷新信号数据 - 通过 RuntimeBus 调度到 SignalRuntime"""
    await _dispatch_refresh(
        command="refresh_signals",
        target="signal_runtime",
        params={"symbol": symbol},
    )

    return {
        "success": True,
        "symbol": symbol,
        "message": "Signal refresh dispatched via RuntimeBus",
        "dispatch_via": "runtime_bus",
        "target": "signal_runtime",
    }


@router.post("/refresh/factors")
async def refresh_factors(
    symbol: str = Query(default="BTCUSDT", description="币种"),
) -> Dict[str, Any]:
    """刷新因子数据 - 通过 RuntimeBus 调度到 FeatureRuntime"""
    await _dispatch_refresh(
        command="refresh_factors",
        target="feature_runtime",
        params={"symbol": symbol},
    )

    return {
        "success": True,
        "symbol": symbol,
        "message": "Factor refresh dispatched via RuntimeBus",
        "dispatch_via": "runtime_bus",
        "target": "feature_runtime",
    }


@router.post("/refresh/news")
async def refresh_news(
    symbol: str = Query(default="BTCUSDT", description="币种"),
) -> Dict[str, Any]:
    """刷新新闻数据 - 通过 RuntimeBus 调度"""
    await _dispatch_refresh(
        command="refresh_news",
        target="data_runtime",
        params={"symbol": symbol},
    )

    return {
        "success": True,
        "symbol": symbol,
        "message": "News refresh dispatched via RuntimeBus",
        "dispatch_via": "runtime_bus",
        "target": "data_runtime",
    }


@router.post("/refresh/correlation")
async def refresh_correlation(
    symbol: str = Query(default="BTCUSDT", description="币种"),
) -> Dict[str, Any]:
    """刷新相关性数据 - 通过 RuntimeBus 调度到 CorrelationRuntime"""
    await _dispatch_refresh(
        command="run_correlation_analysis",
        target="correlation_runtime",
        params={"symbol": symbol},
    )

    return {
        "success": True,
        "symbol": symbol,
        "message": "Correlation refresh dispatched via RuntimeBus",
        "dispatch_via": "runtime_bus",
        "target": "correlation_runtime",
    }


@router.post("/refresh/all")
async def refresh_all(
    symbol: str = Query(default="BTCUSDT", description="币种"),
) -> Dict[str, Any]:
    """刷新所有数据 - 通过 RuntimeBus 调度到所有 Runtime"""
    await _dispatch_refresh("refresh_price", "data_runtime", {"symbol": symbol})
    await _dispatch_refresh("refresh_signals", "signal_runtime", {"symbol": symbol})
    await _dispatch_refresh("refresh_factors", "feature_runtime", {"symbol": symbol})
    await _dispatch_refresh("refresh_news", "data_runtime", {"symbol": symbol})
    await _dispatch_refresh("run_correlation_analysis", "correlation_runtime", {"symbol": symbol})

    return {
        "success": True,
        "symbol": symbol,
        "message": "All refresh commands dispatched via RuntimeBus",
        "dispatch_via": "runtime_bus",
        "targets": [
            "data_runtime",
            "signal_runtime",
            "feature_runtime",
            "correlation_runtime",
        ],
    }


@router.post("/refresh/projection")
async def refresh_projection(
    symbol: str = Query(default="BTCUSDT", description="币种"),
) -> Dict[str, Any]:
    """刷新投影状态 - 通过 RuntimeBus 调度到 ProjectionRuntime"""
    await _dispatch_refresh(
        command="refresh_projection",
        target="projection_runtime",
        params={"symbol": symbol},
    )

    return {
        "success": True,
        "symbol": symbol,
        "message": "Projection refresh dispatched via RuntimeBus",
        "dispatch_via": "runtime_bus",
        "target": "projection_runtime",
    }
