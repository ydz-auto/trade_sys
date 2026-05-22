"""
Execution Router - 执行引擎端点

架构：
    API Router (转发)
      ↓
    ExecutionAPIService (adapter，无状态)
      ↓
    RuntimeBus.publish_command()
      ↓
    ExecutionRuntime (唯一 execution state source)
      ↓
    runtime_bus
"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel, Field

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


def _get_service():
    from api.services.execution_api_service import get_execution_api_service
    return get_execution_api_service()


@router.post("/execution/orders")
async def create_order(request: OrderRequest):
    service = _get_service()
    result = await service.create_order(
        symbol=request.symbol,
        side=request.side,
        quantity=request.quantity,
        order_type=request.order_type,
        price=request.price,
        exchange=request.exchange,
    )
    if not result.get("success") and "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/execution/orders/open")
async def get_open_orders(
    symbol: Optional[str] = Query(None),
    exchange: Optional[str] = Query(None),
):
    service = _get_service()
    orders = await service.get_open_orders(symbol=symbol, exchange=exchange)
    return {"orders": orders, "total": len(orders)}


@router.get("/execution/orders/history")
async def get_order_history(
    symbol: Optional[str] = Query(None),
    limit: int = Query(100),
):
    service = _get_service()
    orders = await service.get_order_history(symbol=symbol, limit=limit)
    return {"orders": orders, "total": len(orders)}


@router.get("/execution/orders/{order_id}")
async def get_order(order_id: str):
    service = _get_service()
    result = await service.get_order(order_id)
    if not result:
        raise HTTPException(status_code=404, detail="Order not found")
    return result


@router.delete("/execution/orders/{order_id}")
async def cancel_order(order_id: str):
    service = _get_service()
    result = await service.cancel_order(order_id)
    return result


@router.get("/execution/positions")
async def get_positions(
    symbol: Optional[str] = Query(None),
    exchange: Optional[str] = Query(None),
):
    service = _get_service()
    positions = await service.get_positions(symbol=symbol, exchange=exchange)
    return {"positions": positions, "total": len(positions)}


@router.post("/execution/positions/{position_id}/close")
async def close_position(
    position_id: str,
    quantity: Optional[float] = Query(None),
):
    service = _get_service()
    result = await service.close_position(position_id, quantity)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Position not found"))
    return result


@router.put("/execution/positions/{position_id}")
async def update_position(position_id: str, updates: PositionUpdate):
    service = _get_service()
    result = await service.update_position(position_id, updates.model_dump(exclude_none=True))
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Position not found"))
    return result


@router.post("/execution/signals/execute")
async def execute_signal(request: SignalExecuteRequest):
    service = _get_service()
    result = await service.execute_signal(
        signal_id=request.signal_id,
        symbol=request.symbol,
        action=request.action,
        quantity=request.quantity,
        confidence=request.confidence,
        exchange=request.exchange,
    )
    return result


@router.post("/execution/signals/batch")
async def execute_signals_batch(request: SignalBatchExecuteRequest):
    service = _get_service()
    signals = [s.model_dump() for s in request.signals]
    return await service.execute_signals_batch(signals)


@router.get("/execution/state")
async def get_execution_state():
    service = _get_service()
    return await service.get_execution_state()
