from fastapi import APIRouter, Query
from typing import Dict, Any

from application.queries.projection import (
    get_projection_full_state,
    get_projection_position,
    get_projection_decision,
    get_projection_risk,
    get_projection_price,
    get_projection_metrics,
)

router = APIRouter()


@router.get("/projection/state")
async def get_projection_state(
    symbol: str = Query(default="BTCUSDT", description="币种"),
) -> Dict[str, Any]:
    state = await get_projection_full_state(symbol=symbol)
    return {"symbol": symbol, "state": state, "source": "projection_runtime"}


@router.get("/projection/position")
async def get_position(
    symbol: str = Query(default="BTCUSDT", description="币种"),
) -> Dict[str, Any]:
    position = await get_projection_position(symbol=symbol)
    return {"symbol": symbol, "position": position, "source": "projection_runtime"}


@router.get("/projection/decision")
async def get_decision(
    symbol: str = Query(default="BTCUSDT", description="币种"),
) -> Dict[str, Any]:
    decision = await get_projection_decision(symbol=symbol)
    return {"symbol": symbol, "decision": decision, "source": "projection_runtime"}


@router.get("/projection/risk")
async def get_risk(
    symbol: str = Query(default="BTCUSDT", description="币种"),
) -> Dict[str, Any]:
    risk = await get_projection_risk(symbol=symbol)
    return {"symbol": symbol, "risk": risk, "source": "projection_runtime"}


@router.get("/projection/price")
async def get_price(
    symbol: str = Query(default="BTCUSDT", description="币种"),
) -> Dict[str, Any]:
    price = await get_projection_price(symbol=symbol)
    return {"symbol": symbol, "price": price, "source": "projection_runtime"}


@router.get("/projection/metrics")
async def get_metrics(
    symbol: str = Query(default="BTCUSDT", description="币种"),
) -> Dict[str, Any]:
    metrics = await get_projection_metrics(symbol=symbol)
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
