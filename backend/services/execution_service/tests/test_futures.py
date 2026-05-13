"""
Binance Futures 测试用例

测试合约功能：
- 杠杆设置
- 合约订单
- reduce_only 平仓
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from domain.execution.models import (
    Order, OrderRequest, OrderIntent,
    OrderSide, OrderType, OrderStatus, Exchange, MarketType
)
from services.execution_service.engine import ExecutionEngine
from services.execution_service.adapters import BinanceFuturesAdapter, MockAdapter
from infrastructure.logging import get_logger

logger = get_logger("test_futures")


async def test_futures_mock():
    """测试合约功能（使用 Mock）"""
    print("=" * 60)
    print("Testing Binance Futures (Mock Mode)")
    print("=" * 60)

    engine = ExecutionEngine()

    adapter = MockAdapter()
    engine.register_adapter(adapter)
    await engine.connect_all()

    print("\n1. Testing Futures Order...")
    result = await engine.execute_futures_order(
        symbol="BTCUSDT",
        side="buy",
        quantity=0.001,
        leverage=5,
    )
    print(f"   Order result: success={result.success}")
    if result.order:
        print(f"   Order ID: {result.order.order_id}")
        print(f"   Status: {result.order.status.value}")
        print(f"   Leverage: {result.order.metadata.get('leverage')}")

    print("\n2. Testing Position Query...")
    positions = await engine.get_positions()
    print(f"   Positions: {len(positions)}")
    for pos in positions:
        print(f"   - {pos.symbol}: qty={pos.quantity}, avg={pos.average_price}, leverage={pos.leverage}")

    print("\n3. Testing Close Position (reduce_only)...")
    close_result = await engine.close_position(
        symbol="BTCUSDT",
        exchange=Exchange.BINANCE,
        market_type=MarketType.USDT_FUTURES,
    )
    print(f"   Close result: success={close_result.success}")
    if close_result.order:
        print(f"   Order ID: {close_result.order.order_id}")
        print(f"   Side: {close_result.order.side.value}")
        print(f"   Reduce Only: {close_result.order.metadata.get('reduce_only')}")

    print("\n4. Testing Limit Order...")
    limit_result = await engine.execute_futures_order(
        symbol="ETHUSDT",
        side="buy",
        quantity=0.1,
        leverage=3,
        order_type="limit",
        price=2000.0,
    )
    print(f"   Limit order result: success={limit_result.success}")

    print("\n5. Testing Short Position...")
    short_result = await engine.execute_futures_order(
        symbol="BTCUSDT",
        side="sell",
        quantity=0.002,
        leverage=10,
    )
    print(f"   Short order result: success={short_result.success}")

    positions = engine.get_local_positions()
    print(f"\n   Final positions: {len(positions)}")
    for pos in positions:
        direction = "LONG" if pos.quantity > 0 else "SHORT"
        print(f"   - {pos.symbol}: {direction} {abs(pos.quantity)} @ {pos.average_price}")

    print("\n6. Testing Order History...")
    history = engine.get_order_history()
    print(f"   Total orders: {len(history)}")
    for order in history[:5]:
        print(f"   - {order.order_id}: {order.side.value} {order.quantity} {order.symbol} [{order.status.value}]")

    print("\n" + "=" * 60)
    print("✅ Futures tests completed!")
    print("=" * 60)


async def test_order_intent_futures():
    """测试使用 OrderIntent 执行合约订单"""
    print("\n" + "=" * 60)
    print("Testing OrderIntent with Futures")
    print("=" * 60)

    engine = ExecutionEngine()
    engine.register_adapter(MockAdapter())
    await engine.connect_all()

    intent = OrderIntent(
        intent_id="test_futures_intent",
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        quantity=0.01,
        exchange=Exchange.BINANCE,
        market_type=MarketType.USDT_FUTURES,
        max_leverage=5,
        stop_loss_pct=0.02,
        take_profit_pct=0.05,
        signal_id="test_signal_001",
    )

    print(f"\nIntent: {intent.to_dict()}")

    result = await engine.execute_intent(intent)

    print(f"\nResult: success={result.success}")
    if result.order:
        print(f"Order: {result.order.order_id}")
        print(f"Type: {result.order.order_type.value}")
        print(f"Status: {result.order.status.value}")
        print(f"Metadata: {result.order.metadata}")


async def main():
    """运行所有测试"""
    await test_futures_mock()
    await test_order_intent_futures()


if __name__ == "__main__":
    asyncio.run(main())
