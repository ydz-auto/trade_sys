"""
Trading Mode Router - 交易模式管理 API

架构：
    API Router (转发)
      ↓
    Application Layer (commands / queries)
      ↓
    Domain / Runtime
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from pydantic import BaseModel, Field

from application.queries.system import (
    get_trading_mode_enum,
    get_trading_mode_status,
    get_all_modes,
    get_trading_mode_portfolio,
    get_trading_mode_stats,
    get_trading_mode_safety,
    preview_mode_transition,
)
from application.commands.mode import transition_mode, set_exchange

TradingMode = get_trading_mode_enum()

router = APIRouter(prefix="/trading-mode", tags=["Trading Mode"])


class TransitionRequest(BaseModel):
    target_mode: str = Field(..., description="目标模式: backtest, paper, live")
    reason: str = Field(default="", description="切换原因")
    confirmed: bool = Field(default=False, description="是否已确认")
    force: bool = Field(default=False, description="强制切换")


@router.get("")
async def get_trading_mode_status_endpoint() -> Dict[str, Any]:
    return get_trading_mode_status()


@router.get("/modes")
async def get_all_modes_endpoint() -> Dict[str, Any]:
    return get_all_modes()


@router.post("/transition")
async def transition_mode_endpoint(request: TransitionRequest) -> Dict[str, Any]:
    try:
        TradingMode(request.target_mode.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {request.target_mode}")

    result = await transition_mode(
        target_mode=request.target_mode.lower(),
        reason=request.reason,
        confirmed=request.confirmed,
        force=request.force,
    )

    if not result.get("success"):
        if result.get("requires_confirmation"):
            return result
        raise HTTPException(status_code=400, detail=result.get("error", "Transition failed"))

    return result


@router.post("/transition/preview")
async def preview_transition_endpoint(request: TransitionRequest) -> Dict[str, Any]:
    try:
        TradingMode(request.target_mode.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {request.target_mode}")

    return await preview_mode_transition(target_mode=request.target_mode.lower())


@router.get("/portfolio")
async def get_portfolio_endpoint(mode: str = None) -> Dict[str, Any]:
    if mode:
        try:
            TradingMode(mode.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid mode: {mode}")
    return get_trading_mode_portfolio(mode=mode)


@router.get("/stats")
async def get_stats_endpoint() -> Dict[str, Any]:
    return get_trading_mode_stats()


@router.post("/exchange")
async def set_exchange_endpoint(request: BaseModel) -> Dict[str, Any]:
    try:
        return set_exchange(exchange=request.model_dump()["exchange"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/safety-check")
async def safety_check_endpoint() -> Dict[str, Any]:
    return get_trading_mode_safety()
