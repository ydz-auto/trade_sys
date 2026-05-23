"""Trading Commands - 交易写操作"""
from typing import Dict, Any, Optional

async def submit_order(
    symbol: str,
    action: str,
    quantity: float,
    order_type: str = "market",
    price: Optional[float] = None,
    leverage: int = 1,
    **kwargs,
) -> Dict[str, Any]:
    from runtime.execution_runtime.runtime import get_execution_runtime
    runtime = get_execution_runtime()
    if runtime and hasattr(runtime, 'submit_order'):
        return await runtime.submit_order(
            symbol=symbol,
            action=action,
            quantity=quantity,
            order_type=order_type,
            price=price,
            leverage=leverage,
            **kwargs,
        )
    return {"success": False, "error": "ExecutionRuntime not available"}

async def cancel_order(order_id: str) -> Dict[str, Any]:
    from runtime.execution_runtime.runtime import get_execution_runtime
    runtime = get_execution_runtime()
    if runtime and hasattr(runtime, 'cancel_order'):
        return await runtime.cancel_order(order_id)
    return {"success": False, "error": "ExecutionRuntime not available"}
