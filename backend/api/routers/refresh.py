"""
Refresh Router - 数据刷新 API 端点

架构：
    API Router (转发)
      ↓
    RuntimeBus.publish_command()
      ↓
    各 Runtime 处理刷新
"""
from fastapi import APIRouter, Query
from typing import Dict, Any

from ..schemas.common import SuccessResponse

router = APIRouter()


async def _dispatch_refresh(command: str, target: str, params: dict):
    from application.commands.bus_commands import publish_command
    await publish_command(
        command_type=command,
        data=params,
        target=target,
    )


@router.post("/refresh/price")
async def refresh_price(symbol: str = Query(default="BTCUSDT")) -> Dict[str, Any]:
    await _dispatch_refresh("refresh_price", "data_runtime", {"symbol": symbol})
    return {"success": True, "symbol": symbol, "dispatch_via": "runtime_bus", "target": "data_runtime"}


@router.post("/refresh/signals")
async def refresh_signals(symbol: str = Query(default="BTCUSDT")) -> Dict[str, Any]:
    await _dispatch_refresh("refresh_signals", "signal_runtime", {"symbol": symbol})
    return {"success": True, "symbol": symbol, "dispatch_via": "runtime_bus", "target": "signal_runtime"}


@router.post("/refresh/factors")
async def refresh_factors(symbol: str = Query(default="BTCUSDT")) -> Dict[str, Any]:
    await _dispatch_refresh("refresh_factors", "feature_runtime", {"symbol": symbol})
    return {"success": True, "symbol": symbol, "dispatch_via": "runtime_bus", "target": "feature_runtime"}


@router.post("/refresh/news")
async def refresh_news(symbol: str = Query(default="BTCUSDT")) -> Dict[str, Any]:
    await _dispatch_refresh("refresh_news", "data_runtime", {"symbol": symbol})
    return {"success": True, "symbol": symbol, "dispatch_via": "runtime_bus", "target": "data_runtime"}


@router.post("/refresh/correlation")
async def refresh_correlation(symbol: str = Query(default="BTCUSDT")) -> Dict[str, Any]:
    await _dispatch_refresh("run_correlation_analysis", "correlation_runtime", {"symbol": symbol})
    return {"success": True, "symbol": symbol, "dispatch_via": "runtime_bus", "target": "correlation_runtime"}


@router.post("/refresh/all")
async def refresh_all(symbol: str = Query(default="BTCUSDT")) -> Dict[str, Any]:
    await _dispatch_refresh("refresh_price", "data_runtime", {"symbol": symbol})
    await _dispatch_refresh("refresh_signals", "signal_runtime", {"symbol": symbol})
    await _dispatch_refresh("refresh_factors", "feature_runtime", {"symbol": symbol})
    await _dispatch_refresh("run_correlation_analysis", "correlation_runtime", {"symbol": symbol})
    return {
        "success": True,
        "symbol": symbol,
        "dispatch_via": "runtime_bus",
        "targets": ["data_runtime", "signal_runtime", "feature_runtime", "correlation_runtime"],
    }


@router.post("/refresh/projection")
async def refresh_projection(symbol: str = Query(default="BTCUSDT")) -> Dict[str, Any]:
    await _dispatch_refresh("refresh_projection", "projection_runtime", {"symbol": symbol})
    return {"success": True, "symbol": symbol, "dispatch_via": "runtime_bus", "target": "projection_runtime"}
