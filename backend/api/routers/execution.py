"""
Execution Router - 执行引擎端点

架构：
    API Router
      ↓
    RuntimeBus (publish_command)
      ↓
    ExecutionRuntime
      ↓
    runtime_bus
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel, Field

router = APIRouter()


class OrderRequest(BaseModel):
    symbol: str = Field(..., description="交易对，如 BTCUSDT")
    side: str = Field(..., description="方向 buy/sell")
    quantity: float = Field(..., description="数量")
    order_type: str = Field(default="market", description="订单类型 market/limit")
    price: Optional[float] = Field(None, description="价格（限价单需要）")
    exchange: str = Field(default="binance", description="交易所")


class OrderResponse(BaseModel):
    order_id: str
    symbol: str
    side: str
    quantity: float
    order_type: str
    price: Optional[float]
    exchange: str
    status: str
    filled_quantity: float
    average_price: float
    created_at: str
    updated_at: str


class PositionUpdate(BaseModel):
    quantity: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    notes: Optional[str] = None


class SignalExecuteRequest(BaseModel):
    signal_id: str = Field(..., description="信号ID")
    symbol: str = Field(..., description="币种")
    action: str = Field(..., description="操作 buy/sell")
    quantity: float = Field(..., description="数量")
    confidence: float = Field(default=1.0, description="置信度")
    exchange: str = Field(default="binance", description="交易所")


class SignalBatchExecuteRequest(BaseModel):
    signals: List[SignalExecuteRequest]


async def _get_execution_api_service():
    from ..services.execution_api_service import get_execution_api_service
    return get_execution_api_service()


async def _dispatch_to_execution_runtime(command: str, params: dict):
    from runtime.bus.runtime_bus import get_runtime_bus

    bus = get_runtime_bus()
    await bus.publish_command(
        command=command,
        target="execution_runtime",
        params=params,
        source="api.execution",
    )


@router.post("/execution/orders", response_model=OrderResponse)
async def create_order(request: OrderRequest):
    """下单 - 通过 RuntimeBus 调度到 ExecutionRuntime"""
    await _dispatch_to_execution_runtime("create_order", {
        "symbol": request.symbol,
        "side": request.side,
        "quantity": request.quantity,
        "order_type": request.order_type,
        "price": request.price,
        "exchange": request.exchange,
    })

    service = await _get_execution_api_service()
    result = await service.create_order(
        symbol=request.symbol,
        side=request.side,
        quantity=request.quantity,
        order_type=request.order_type,
        price=request.price,
        exchange=request.exchange,
    )
    return OrderResponse(**result)


@router.get("/execution/orders/open", response_model=List[OrderResponse])
async def get_open_orders(
    symbol: Optional[str] = Query(None, description="币种过滤"),
    exchange: Optional[str] = Query(None, description="交易所过滤"),
):
    """获取未完成订单"""
    service = await _get_execution_api_service()
    orders = await service.get_open_orders(symbol=symbol, exchange=exchange)
    return [OrderResponse(**o) for o in orders]


@router.get("/execution/orders/history", response_model=List[OrderResponse])
async def get_order_history(
    symbol: Optional[str] = Query(None, description="币种过滤"),
    limit: int = Query(100, description="返回数量"),
):
    """获取订单历史"""
    service = await _get_execution_api_service()
    orders = await service.get_order_history(symbol=symbol, limit=limit)
    return [OrderResponse(**o) for o in orders]


@router.get("/execution/orders/{order_id}", response_model=OrderResponse)
async def get_order(order_id: str):
    """获取订单详情"""
    service = await _get_execution_api_service()
    result = await service.get_order(order_id)
    if not result:
        raise HTTPException(status_code=404, detail="Order not found")
    return OrderResponse(**result)


@router.delete("/execution/orders/{order_id}")
async def cancel_order(order_id: str):
    """取消订单 - 通过 RuntimeBus 调度"""
    await _dispatch_to_execution_runtime("cancel_order", {
        "order_id": order_id,
    })

    service = await _get_execution_api_service()
    result = await service.cancel_order(order_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to cancel order"))
    return result


@router.get("/execution/positions")
async def get_positions(
    symbol: Optional[str] = Query(None, description="币种过滤"),
    exchange: Optional[str] = Query(None, description="交易所过滤"),
):
    """获取持仓列表"""
    service = await _get_execution_api_service()
    positions = await service.get_positions(symbol=symbol, exchange=exchange)
    return {
        "positions": positions,
        "total": len(positions),
    }


@router.post("/execution/positions/{position_id}/close")
async def close_position(
    position_id: str,
    quantity: Optional[float] = Query(None, description="平仓数量（可选）"),
):
    """平仓 - 通过 RuntimeBus 调度"""
    await _dispatch_to_execution_runtime("close_position", {
        "position_id": position_id,
        "quantity": quantity,
    })

    service = await _get_execution_api_service()
    result = await service.close_position(position_id, quantity)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result.get("error", "Position not found"))
    return result


@router.put("/execution/positions/{position_id}")
async def update_position(position_id: str, updates: PositionUpdate):
    """更新持仓"""
    service = await _get_execution_api_service()
    update_dict = updates.model_dump(exclude_none=True)
    result = await service.update_position(position_id, update_dict)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result.get("error", "Position not found"))
    return result


@router.post("/execution/signals/execute")
async def execute_signal(request: SignalExecuteRequest):
    """执行信号 - 通过 RuntimeBus 调度到 ExecutionRuntime"""
    await _dispatch_to_execution_runtime("execute_signal", {
        "signal_id": request.signal_id,
        "symbol": request.symbol,
        "action": request.action,
        "quantity": request.quantity,
        "confidence": request.confidence,
        "exchange": request.exchange,
    })

    service = await _get_execution_api_service()
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
    """批量执行信号 - 通过 RuntimeBus 调度"""
    signals = [s.model_dump() for s in request.signals]

    for signal in signals:
        await _dispatch_to_execution_runtime("execute_signal", signal)

    service = await _get_execution_api_service()
    result = await service.execute_signals_batch(signals)
    return result


@router.get("/execution/state")
async def get_execution_state():
    """获取执行状态"""
    service = await _get_execution_api_service()
    return await service.get_execution_state()
