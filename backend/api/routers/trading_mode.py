"""
Trading Mode Router - 交易模式管理 API

架构：
    API Router (转发)
      ↓
    RuntimeCommandBus.execute(SWITCH_MODE)
      ↓
    RuntimeOrchestrator
      ↓
    RuntimeBus
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from pydantic import BaseModel, Field

from domain.trading_mode import (
    TradingMode,
    get_trading_mode_manager,
)

router = APIRouter(prefix="/trading-mode", tags=["Trading Mode"])


class TransitionRequest(BaseModel):
    target_mode: str = Field(..., description="目标模式: backtest, paper, live")
    reason: str = Field(default="", description="切换原因")
    confirmed: bool = Field(default=False, description="是否已确认")
    force: bool = Field(default=False, description="强制切换")


@router.get("")
async def get_trading_mode_status() -> Dict[str, Any]:
    manager = get_trading_mode_manager()
    status = manager.get_status()
    config = manager.config
    return {
        "mode": status.mode.value,
        "state": status.state.value,
        "previous_mode": status.previous_mode.value if status.previous_mode else None,
        "config": {
            "market_data_source": config.market_data_source,
            "order_execution": config.order_execution,
            "risk_engine": config.risk_engine,
            "portfolio_isolated": config.portfolio_isolated,
            "require_confirmation": config.require_confirmation,
            "color": config.color,
            "warning": config.warning,
        },
        "is_safe_to_trade": manager.is_safe_to_trade(),
    }


@router.get("/modes")
async def get_all_modes() -> Dict[str, Any]:
    manager = get_trading_mode_manager()
    modes = manager.get_all_modes_info()
    return {"modes": modes, "current_mode": manager.mode.value}


@router.post("/transition")
async def transition_mode(request: TransitionRequest) -> Dict[str, Any]:
    from runtime.command.command_bus import get_command_bus, CommandType

    try:
        target_mode = TradingMode(request.target_mode.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {request.target_mode}")

    bus = get_command_bus()
    cmd_result = await bus.execute(
        CommandType.SWITCH_MODE,
        {"target_mode": request.target_mode.lower(), "reason": request.reason, "confirmed": request.confirmed},
        source="api.trading_mode",
    )

    if cmd_result.success:
        return {
            "success": True,
            "mode": request.target_mode.lower(),
            "message": "Mode transition dispatched via RuntimeCommandBus",
            "dispatch_via": "runtime_command_bus",
        }

    manager = get_trading_mode_manager()
    result = await manager.transition_to(
        target_mode=target_mode,
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
async def preview_transition(request: TransitionRequest) -> Dict[str, Any]:
    manager = get_trading_mode_manager()
    try:
        target_mode = TradingMode(request.target_mode.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {request.target_mode}")

    can_transition, message = await manager.can_transition_to(target_mode)
    target_config = manager.get_all_modes_info()
    target_info = next((m for m in target_config if m["mode"] == target_mode.value), None)

    return {
        "can_transition": can_transition,
        "message": message,
        "current_mode": manager.mode.value,
        "target_mode": target_mode.value,
        "target_config": target_info["config"] if target_info else None,
        "requires_confirmation": target_info["config"]["require_confirmation"] if target_info else False,
    }


@router.get("/portfolio")
async def get_portfolio(mode: str = None) -> Dict[str, Any]:
    manager = get_trading_mode_manager()
    target_mode = None
    if mode:
        try:
            target_mode = TradingMode(mode.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid mode: {mode}")
    portfolio = manager.get_portfolio(target_mode)
    return {"mode": (target_mode or manager.mode).value, "portfolio": portfolio}


@router.get("/stats")
async def get_stats() -> Dict[str, Any]:
    return get_trading_mode_manager().get_stats()


@router.post("/exchange")
async def set_exchange(request: BaseModel) -> Dict[str, Any]:
    manager = get_trading_mode_manager()
    try:
        manager.set_exchange(request.model_dump()["exchange"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True, "exchange": request.model_dump()["exchange"], "mode": manager.mode.value}


@router.get("/safety-check")
async def safety_check() -> Dict[str, Any]:
    manager = get_trading_mode_manager()
    is_safe, message = manager.is_safe_to_trade()
    return {"is_safe": is_safe, "message": message, "mode": manager.mode.value, "state": manager.state.value}
