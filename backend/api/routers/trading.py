"""Trading Router - 完整交易管理端点

架构：
    API Router (转发)
      ↓
    Application Commands/Queries
      ↓
    RuntimeBus / Runtime
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

from application.commands.trading import (
    submit_order,
    cancel_order,
    close_position,
    set_leverage,
    set_stop_loss_take_profit,
    adjust_position,
    check_stop_loss_take_profit,
)
from application.queries.portfolio import (
    get_portfolio_state,
    get_positions,
    get_accounts,
    get_trading_status,
)
from application.queries.execution import get_execution_state

router = APIRouter()


@router.get("/trading/health", response_model=HealthCheck)
async def health_check():
    from application.commands.bus_commands import publish_command

    try:
        await publish_command(
            command_type="health_check",
            data={},
            target="portfolio_runtime",
        )
        return HealthCheck(status="healthy", state_source="portfolio_runtime")
    except Exception:
        return HealthCheck(status="degraded", state_source="unavailable")


@router.get("/trading/accounts", response_model=AccountBalancesResponse)
async def get_accounts_endpoint():
    accounts = await get_accounts()

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
    status = await get_trading_status()
    positions = await get_positions()
    exec_state = await get_execution_state()
    orders = exec_state.get("orders", {})

    return TradingStatusResponse(
        mode=status["mode"],
        auto_approve_threshold=0,
        total_equity=status["total_equity"],
        total_unrealized_pnl=status["total_unrealized_pnl"],
        total_realized_pnl=0,
        daily_pnl=0,
        positions=[PositionResponse(**p) for p in positions if p.get("side")],
        total_position_value=status["total_position_value"],
        open_orders=[OrderResponse(**o) for o in orders.values() if o.get("status") != "filled"],
        margin_balance=0,
        available_balance=0,
        total_leverage=0,
        max_leverage=125,
    )


@router.get("/trading/positions", response_model=List[PositionResponse])
async def get_positions_endpoint():
    positions = await get_positions()
    return [PositionResponse(**p) for p in positions if p.get("side")]


@router.get("/trading/orders", response_model=List[OrderResponse])
async def get_orders():
    exec_state = await get_execution_state()
    orders = exec_state.get("orders", {})
    return [OrderResponse(**o) for o in orders.values()]


@router.post("/trading/order", response_model=OrderResponse)
async def place_order(request: OrderRequest):
    result = await submit_order(
        symbol=request.symbol,
        action=request.side,
        quantity=request.quantity,
        order_type=request.order_type,
        price=request.price,
    )
    return OrderResponse(**result)


@router.post("/trading/close", response_model=dict)
async def close_position_endpoint(request: ClosePositionRequest):
    try:
        result = await close_position(
            symbol=request.symbol,
            quantity=request.quantity,
        )
        return {"success": True, **result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/trading/leverage", response_model=dict)
async def set_leverage_endpoint(request: SetLeverageRequest):
    try:
        result = await set_leverage(
            symbol=request.symbol,
            leverage=request.leverage,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/trading/stop-loss-take-profit", response_model=dict)
async def set_stop_loss_take_profit_endpoint(request: SetStopLossTakeProfitRequest):
    try:
        result = await set_stop_loss_take_profit(
            symbol=request.symbol,
            stop_loss_pct=request.stop_loss_pct if hasattr(request, 'stop_loss_pct') else None,
            take_profit_pct=request.take_profit_pct if hasattr(request, 'take_profit_pct') else None,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/trading/adjust-position", response_model=dict)
async def adjust_position_endpoint(request: AdjustPositionRequest):
    try:
        result = await adjust_position(
            symbol=request.symbol,
            new_quantity=request.new_quantity if hasattr(request, 'new_quantity') else None,
            new_leverage=request.new_leverage if hasattr(request, 'new_leverage') else None,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/trading/check-sl-tp", response_model=dict)
async def check_sl_tp():
    result = await check_stop_loss_take_profit()
    return result


@router.post("/trading/mode", response_model=dict)
async def set_mode(request: SetTradingModeRequest):
    from application.commands.mode import switch_mode
    result = await switch_mode(
        target_mode=request.mode.value,
        reason="api_request",
    )
    return {"success": True, "mode": result}
