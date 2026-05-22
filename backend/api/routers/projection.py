"""
Projection Router - Runtime 状态 API

架构：
    API Router
      ↓
    ProjectionReader (读取 Redis 中 ProjectionRuntime 写入的状态)
      ↓
    ProjectionRuntime (写入方，通过 RuntimeBus)

注意：这是 CQRS 的读取端，ProjectionReader 读取 ProjectionRuntime 写入的状态，
这是正确的架构模式。写入操作通过 RuntimeBus 调度到 ProjectionRuntime。
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, Dict, Any

from ..services.projection_reader import get_projection_reader

router = APIRouter()


def _get_reader():
    return get_projection_reader()


@router.get("/projection/state")
async def get_projection_state(
    symbol: str = Query(default="BTCUSDT", description="币种"),
) -> Dict[str, Any]:
    """获取完整投影状态"""
    reader = _get_reader()
    state = await reader.get_full_state(symbol=symbol)
    return {
        "symbol": symbol,
        "state": state,
        "source": "projection_runtime",
    }


@router.get("/projection/position")
async def get_position(
    symbol: str = Query(default="BTCUSDT", description="币种"),
) -> Dict[str, Any]:
    """获取持仓状态"""
    reader = _get_reader()
    position = await reader.get_position(symbol=symbol)
    return {
        "symbol": symbol,
        "position": position,
        "source": "projection_runtime",
    }


@router.get("/projection/decision")
async def get_decision(
    symbol: str = Query(default="BTCUSDT", description="币种"),
) -> Dict[str, Any]:
    """获取决策状态"""
    reader = _get_reader()
    decision = await reader.get_decision(symbol=symbol)
    return {
        "symbol": symbol,
        "decision": decision,
        "source": "projection_runtime",
    }


@router.get("/projection/risk")
async def get_risk(
    symbol: str = Query(default="BTCUSDT", description="币种"),
) -> Dict[str, Any]:
    """获取风险状态"""
    reader = _get_reader()
    risk = await reader.get_risk(symbol=symbol)
    return {
        "symbol": symbol,
        "risk": risk,
        "source": "projection_runtime",
    }


@router.get("/projection/price")
async def get_price(
    symbol: str = Query(default="BTCUSDT", description="币种"),
) -> Dict[str, Any]:
    """获取价格状态"""
    reader = _get_reader()
    price = await reader.get_price(symbol=symbol)
    return {
        "symbol": symbol,
        "price": price,
        "source": "projection_runtime",
    }


@router.get("/projection/metrics")
async def get_metrics(
    symbol: str = Query(default="BTCUSDT", description="币种"),
) -> Dict[str, Any]:
    """获取性能指标"""
    reader = _get_reader()
    metrics = await reader.get_metrics(symbol=symbol)
    return {
        "symbol": symbol,
        "metrics": metrics,
        "source": "projection_runtime",
    }


@router.post("/projection/refresh")
async def refresh_projection(
    symbol: str = Query(default="BTCUSDT", description="币种"),
) -> Dict[str, Any]:
    """刷新投影状态 - 通过 RuntimeBus 调度到 ProjectionRuntime"""
    from runtime.bus.runtime_bus import get_runtime_bus

    bus = get_runtime_bus()
    await bus.publish_command(
        command="refresh_projection",
        target="projection_runtime",
        params={"symbol": symbol},
        source="api.projection",
    )

    return {
        "success": True,
        "symbol": symbol,
        "message": "Projection refresh dispatched via RuntimeBus",
        "dispatch_via": "runtime_bus",
        "target": "projection_runtime",
    }
