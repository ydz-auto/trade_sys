"""
Trading Router - 完整交易管理端点
"""
from fastapi import APIRouter, HTTPException
from typing import List

from ..schemas.trading import (
    OrderRequest,
    OrderResponse,
    PositionResponse,
    ClosePositionRequest,
    TradingStatusResponse,
    SetTradingModeRequest,
    SetLeverageRequest,
    SetStopLossTakeProfitRequest,
    AdjustPositionRequest,
    HealthCheck,
    AccountBalancesResponse,
    ExchangeAccount,
)

from ..services.trading_service import get_trading_service

router = APIRouter()


async def get_service():
    service = get_trading_service()
    await service.ensure_connection()
    return service


@router.get("/trading/health", response_model=HealthCheck)
async def health_check():
    """交易系统健康检查"""
    service = await get_service()
    result = await service.health_check()
    return HealthCheck(**result)


@router.get("/trading/accounts", response_model=AccountBalancesResponse)
async def get_accounts():
    """获取所有账户余额"""
    service = await get_service()
    accounts = await service.get_accounts()

    account_list = []
    total_equity = 0

    for key, acc in accounts.items():
        account = ExchangeAccount(
            exchange=acc.get("exchange", key.split("_")[0]),
            market_type=acc.get("market_type", "spot"),
            balance=acc.get("balance", 0),
            available_balance=acc.get("available_balance", 0),
            margin_balance=acc.get("margin_balance", 0),
            unrealized_pnl=acc.get("unrealized_pnl", 0),
            positions_count=acc.get("positions_count", 0),
        )
        account_list.append(account)
        total_equity += acc.get("balance", 0) + acc.get("unrealized_pnl", 0)

    return AccountBalancesResponse(
        total_equity=round(total_equity, 2),
        accounts=account_list,
    )


@router.get("/trading/status", response_model=TradingStatusResponse)
async def get_status():
    """获取交易状态"""
    service = await get_service()
    status = await service.get_trading_status()

    positions = await service.get_positions()
    orders = await service.get_open_orders()

    return TradingStatusResponse(
        mode=status["mode"],
        auto_approve_threshold=status["auto_approve_threshold"],
        total_equity=status["total_equity"],
        total_unrealized_pnl=status["total_unrealized_pnl"],
        total_realized_pnl=status["total_realized_pnl"],
        daily_pnl=status["daily_pnl"],
        positions=[PositionResponse(**p) for p in positions if p.get("side")],
        total_position_value=status["total_position_value"],
        open_orders=[OrderResponse(**o) for o in orders if o.get("status") != "filled"],
        margin_balance=status["margin_balance"],
        available_balance=status["available_balance"],
        total_leverage=0,
        max_leverage=125,
    )


@router.get("/trading/positions", response_model=List[PositionResponse])
async def get_positions():
    """获取持仓列表"""
    service = await get_service()
    positions = await service.get_positions()
    return [PositionResponse(**p) for p in positions if p.get("side")]


@router.get("/trading/orders", response_model=List[OrderResponse])
async def get_orders():
    """获取订单列表"""
    service = await get_service()
    orders = await service.get_open_orders()
    return [OrderResponse(**o) for o in orders]


@router.post("/trading/order", response_model=OrderResponse)
async def place_order(request: OrderRequest):
    """下单"""
    service = await get_service()
    order = await service.place_order(request.model_dump())
    return OrderResponse(**order)


@router.post("/trading/close", response_model=dict)
async def close_position(request: ClosePositionRequest):
    """平仓"""
    service = await get_service()
    try:
        result = await service.close_position(request.model_dump())
        return {"success": True, **result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/trading/leverage", response_model=dict)
async def set_leverage(request: SetLeverageRequest):
    """设置杠杆"""
    service = await get_service()
    try:
        result = await service.set_leverage(request.model_dump())
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/trading/stop-loss-take-profit", response_model=dict)
async def set_stop_loss_take_profit(request: SetStopLossTakeProfitRequest):
    """设置止盈止损"""
    service = await get_service()
    try:
        result = await service.set_stop_loss_take_profit(request.model_dump())
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/trading/adjust-position", response_model=dict)
async def adjust_position(request: AdjustPositionRequest):
    """调整仓位"""
    service = await get_service()
    try:
        result = await service.adjust_position(request.model_dump())
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/trading/check-sl-tp", response_model=dict)
async def check_sl_tp():
    """检查并触发止盈止损"""
    service = await get_service()
    triggered = await service.check_stop_loss_take_profit()
    return {"triggered": triggered, "count": len(triggered)}


@router.post("/trading/mode", response_model=dict)
async def set_mode(request: SetTradingModeRequest):
    """设置交易模式"""
    service = await get_service()
    result = await service.set_trading_mode(
        request.mode.value,
        request.auto_approve_threshold
    )
    return {"success": True, "mode": result}
