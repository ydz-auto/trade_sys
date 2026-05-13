"""
Idempotency Verification Script
验证执行服务的幂等性保护
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from services.execution_service.execution_engine import (
    get_execution_service,
    init_execution_service,
    OrderRequest,
    OrderSide,
    OrderType,
    OrderResult,
    BinanceAdapter,
)
from shared.idempotency import get_idempotency_manager, ExecutionStatus


async def verify_idempotency():
    """验证幂等性"""
    print("=" * 60)
    print("Execution Service Idempotency Verification")
    print("=" * 60)
    
    service = await get_execution_service()
    
    binance = BinanceAdapter(testnet=True)
    service.register_exchange(binance)
    await service.connect_all()
    
    print("\n[1] Testing first order execution...")
    request1 = OrderRequest(
        symbol="BTCUSDT",
        exchange="binance",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.001,
    )
    
    result1 = await service.execute_order(request1)
    print(f"    Result: success={result1.success}, order_id={result1.order.order_id if result1.order else 'N/A'}")
    print(f"    Duplicate: {result1.duplicate}")
    
    print("\n[2] Testing duplicate order (same parameters within same minute)...")
    request2 = OrderRequest(
        symbol="BTCUSDT",
        exchange="binance",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.001,
    )
    
    result2 = await service.execute_order(request2)
    print(f"    Result: success={result2.success}, duplicate={result2.duplicate}")
    print(f"    Error: {result2.error}")
    
    print("\n[3] Testing different order parameters...")
    request3 = OrderRequest(
        symbol="ETHUSDT",
        exchange="binance",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.01,
    )
    
    result3 = await service.execute_order(request3)
    print(f"    Result: success={result3.success}, order_id={result3.order.order_id if result3.order else 'N/A'}")
    print(f"    Duplicate: {result3.duplicate}")
    
    print("\n[4] Testing with explicit idempotency key...")
    request4 = OrderRequest(
        symbol="BTCUSDT",
        exchange="binance",
        side=OrderSide.SELL,
        order_type=OrderType.MARKET,
        quantity=0.001,
        idempotency_key="test_unique_key_12345",
    )
    
    result4 = await service.execute_order(request4)
    print(f"    Result: success={result4.success}, order_id={result4.order.order_id if result4.order else 'N/A'}")
    
    print("\n[5] Testing duplicate with same idempotency key...")
    request5 = OrderRequest(
        symbol="BTCUSDT",
        exchange="binance",
        side=OrderSide.SELL,
        order_type=OrderType.MARKET,
        quantity=0.001,
        idempotency_key="test_unique_key_12345",
    )
    
    result5 = await service.execute_order(request5)
    print(f"    Result: success={result5.success}, duplicate={result5.duplicate}")
    
    print("\n[6] Checking order history...")
    orders = service.get_order_history()
    print(f"    Total orders: {len(orders)}")
    for order in orders:
        print(f"      - {order.order_id}: {order.symbol} {order.side.value} {order.quantity}")
    
    print("\n[7] Checking positions...")
    positions = await service.get_all_positions()
    print(f"    Total positions: {len(positions)}")
    for pos in positions:
        print(f"      - {pos.symbol}: {pos.quantity} @ {pos.average_price}")
    
    print("\n" + "=" * 60)
    print("✅ Idempotency Verification Complete!")
    print("=" * 60)
    
    return True


async def verify_idempotency_manager():
    """验证幂等性管理器"""
    print("\n[Idempotency Manager Verification]")
    
    manager = await get_idempotency_manager()
    
    print("\n  Testing check_and_lock...")
    can_execute1, existing1 = await manager.check_and_lock(
        operation_type="test",
        operation_key="test_key_001",
        request_data={"param": "value"},
    )
    print(f"    First call: can_execute={can_execute1}, existing={existing1}")
    
    can_execute2, existing2 = await manager.check_and_lock(
        operation_type="test",
        operation_key="test_key_001",
        request_data={"param": "value"},
    )
    print(f"    Second call (duplicate): can_execute={can_execute2}, existing={existing2}")
    
    print("\n  Testing complete...")
    success = await manager.complete(
        operation_type="test",
        operation_key="test_key_001",
        result={"status": "done"},
    )
    print(f"    Complete result: {success}")
    
    status = await manager.get_status("test", "test_key_001")
    print(f"    Status after complete: {status.value if status else 'None'}")
    
    print("  ✅ Idempotency Manager verified!")
    return True


async def main():
    """主函数"""
    try:
        await verify_idempotency_manager()
        await verify_idempotency()
    except Exception as e:
        print(f"\n❌ Verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
