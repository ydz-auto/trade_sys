"""
Projection Router - Runtime 状态读取 API

架构：
    API Router (只读)
      ↓
    ProjectionReader (CQRS 读端，从 Redis 读取 Runtime 写入的状态)
      ↓
    ProjectionRuntime (写入端，通过 RuntimeBus)

注意：
- 这是 CQRS 的读取端，只从 Redis 读取，不写
- 写入操作通过 RuntimeBus 调度到 ProjectionRuntime
- ProjectionReader 不维护任何 state
"""
from fastapi import APIRouter, Query
from typing import Dict, Any

from ..services.projection_reader import get_projection_reader

router = APIRouter()


@router.get("/projection/state")
async def get_projection_state(
    symbol: str = Query(default="BTCUSDT", description="币种"),
) -> Dict[str, Any]:
    reader = get_projection_reader()
    state = await reader.get_full_state(symbol=symbol)
    return {"symbol": symbol, "state": state, "source": "projection_runtime"}


@router.get("/projection/position")
async def get_position(
    symbol: str = Query(default="BTCUSDT", description="币种"),
) -> Dict[str, Any]:
    reader = get_projection_reader()
    position = await reader.get_position(symbol=symbol)
    return {"symbol": symbol, "position": position, "source": "projection_runtime"}


@router.get("/projection/decision")
async def get_decision(
    symbol: str = Query(default="BTCUSDT", description="币种"),
) -> Dict[str, Any]:
    reader = get_projection_reader()
    decision = await reader.get_decision(symbol=symbol)
    return {"symbol": symbol, "decision": decision, "source": "projection_runtime"}


@router.get("/projection/risk")
async def get_risk(
    symbol: str = Query(default="BTCUSDT", description="币种"),
) -> Dict[str, Any]:
    reader = get_projection_reader()
    risk = await reader.get_risk(symbol=symbol)
    return {"symbol": symbol, "risk": risk, "source": "projection_runtime"}


@router.get("/projection/price")
async def get_price(
    symbol: str = Query(default="BTCUSDT", description="币种"),
) -> Dict[str, Any]:
    reader = get_projection_reader()
    price = await reader.get_price(symbol=symbol)
    return {"symbol": symbol, "price": price, "source": "projection_runtime"}


@router.get("/projection/metrics")
async def get_metrics(
    symbol: str = Query(default="BTCUSDT", description="币种"),
) -> Dict[str, Any]:
    reader = get_projection_reader()
    metrics = await reader.get_metrics(symbol=symbol)
    return {"symbol": symbol, "metrics": metrics, "source": "projection_runtime"}


@router.post("/projection/refresh")
async def refresh_projection(
    symbol: str = Query(default="BTCUSDT", description="币种"),
) -> Dict[str, Any]:
    from application.commands.bus_commands import publish_command

    await publish_command(
        command_type="refresh_projection",
        data={"symbol": symbol},
        target="projection_runtime",
    )

    return {
        "success": True,
        "symbol": symbol,
        "message": "Projection refresh dispatched via RuntimeBus",
        "dispatch_via": "runtime_bus",
        "target": "projection_runtime",
    }
