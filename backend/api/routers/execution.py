"""Execution Router - 执行引擎端点

架构：
    API Router (转发)
      ↓
    Application Commands/Queries
      ↓
    RuntimeBus / ExecutionRuntime
"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel, Field

from application.commands.trading import submit_order, cancel_order
from application.commands.bus_commands import publish_command
from application.queries.execution import (
    get_execution_state,
    get_open_orders,
    get_orders,
    get_order,
)
from application.queries.portfolio import get_positions

router = APIRouter()


class OrderRequest(BaseModel):
    symbol: str
    side: str
    quantity: float
    order_type: str = "market"
    price: Optional[float] = None
    exchange: str = "binance"


class PositionUpdate(BaseModel):
    quantity: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    notes: Optional[str] = None


class SignalExecuteRequest(BaseModel):
    signal_id: str
    symbol: str
    action: str
    quantity: float
    confidence: float = 1.0
    exchange: str = "binance"


class SignalBatchExecuteRequest(BaseModel):
    signals: List[SignalExecuteRequest]


@router.post("/execution/orders")
async def create_order(request: OrderRequest):
    result = await submit_order(
        symbol=request.symbol,
        action=request.side,
        quantity=request.quantity,
        order_type=request.order_type,
        price=request.price,
        exchange=request.exchange,
    )
    if not result.get("success") and "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/execution/orders/open")
async def get_open_orders_endpoint(
    symbol: Optional[str] = Query(None),
    exchange: Optional[str] = Query(None),
):
    orders = await get_open_orders(symbol=symbol, exchange=exchange)
    return {"orders": orders, "total": len(orders)}


@router.get("/execution/orders/history")
async def get_order_history(
    symbol: Optional[str] = Query(None),
    limit: int = Query(100),
):
    orders = await get_orders(symbol=symbol)
    orders.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return {"orders": orders[:limit], "total": len(orders)}


@router.get("/execution/orders/{order_id}")
async def get_order_endpoint(order_id: str):
    result = await get_order(order_id)
    if not result:
        raise HTTPException(status_code=404, detail="Order not found")
    return result


@router.delete("/execution/orders/{order_id}")
async def cancel_order_endpoint(order_id: str):
    result = await cancel_order(order_id)
    return result


@router.get("/execution/positions")
async def get_positions_endpoint(
    symbol: Optional[str] = Query(None),
    exchange: Optional[str] = Query(None),
):
    positions = await get_positions(symbol=symbol, exchange=exchange)
    return {"positions": positions, "total": len(positions)}


@router.post("/execution/positions/{position_id}/close")
async def close_position(
    position_id: str,
    quantity: Optional[float] = Query(None),
):
    await publish_command(
        command_type="close_position",
        data={"position_id": position_id, "quantity": quantity},
        target="portfolio_runtime",
    )
    return {"success": True, "position_id": position_id, "dispatch_via": "runtime_bus"}


@router.put("/execution/positions/{position_id}")
async def update_position(position_id: str, updates: PositionUpdate):
    await publish_command(
        command_type="update_position",
        data={"position_id": position_id, "updates": updates.model_dump(exclude_none=True)},
        target="portfolio_runtime",
    )
    return {"success": True, "position_id": position_id, "dispatch_via": "runtime_bus"}


@router.post("/execution/signals/execute")
async def execute_signal(request: SignalExecuteRequest):
    result = await submit_order(
        symbol=request.symbol,
        action=request.action,
        quantity=request.quantity,
        exchange=request.exchange,
    )
    return {
        **result,
        "signal_id": request.signal_id,
        "confidence": request.confidence,
    }


@router.post("/execution/signals/batch")
async def execute_signals_batch(request: SignalBatchExecuteRequest):
    results = []
    errors = []
    for signal in request.signals:
        try:
            result = await submit_order(
                symbol=signal.symbol,
                action=signal.action,
                quantity=signal.quantity,
                exchange=signal.exchange,
            )
            if result.get("success", True):
                results.append({**result, "signal_id": signal.signal_id})
            else:
                errors.append({"signal": signal.model_dump(), "error": result.get("error", "Unknown")})
        except Exception as e:
            errors.append({"signal": signal.model_dump(), "error": str(e)})
    return {"total": len(request.signals), "executed": len(results), "failed": len(errors), "results": results, "errors": errors}


@router.get("/execution/state")
async def get_execution_state_endpoint():
    exec_state = await get_execution_state()
    portfolio_state = await get_positions()
    return {
        "state": exec_state.get("state", "unknown"),
        "last_error": exec_state.get("last_error"),
        "orders_count": len(exec_state.get("orders", {})),
        "positions_count": len(portfolio_state),
        "source": "runtime",
    }
