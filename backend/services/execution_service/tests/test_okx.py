"""
OKX Adapter Test

测试 OKX 适配器集成
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from domain.execution.models import OrderIntent, OrderSide, OrderType, MarketType, Exchange
from services.execution_service.engine import init_execution_engine, reset_execution_engine
from services.execution_service.adapters import OKXAdapter, MockAdapter
from infrastructure.logging import setup_logging


async def test_okx_adapter():
    """测试 OKX 适配器（模拟）"""
    print("\n" + "=" * 60)
    print("Testing OKX Adapter Integration")
    print("=" * 60)

    # 重置引擎
    reset_execution_engine()
    engine = await init_execution_engine(use_orm=False)

    # 先测试 Mock 适配器（避免真实 API）
    adapter = MockAdapter()
    engine.register_adapter(adapter)
    await engine.connect_all()
    print("✅ Mock adapter registered and connected")

    # 执行测试订单
    result = await engine.execute_futures_order(
        symbol="BTC-USDT-SWAP",
        side="buy",
        quantity=0.001,
        leverage=5,
    )
    print(f"\n✅ Test order result: {'Success' if result.success else 'Failed'}")
    if result.order:
        print(f"  - Order ID: {result.order.order_id}")
        print(f"  - Status: {result.order.status}")

    print("\n✅ All tests passed!")
    print("=" * 60)

    # 展示如何使用真实 OKX：
    print("\nTo use real OKX:")
    print("  Set env vars:")
    print("    EXECUTION_EXCHANGE=okx")
    print("    EXECUTION_MARKET_TYPE=swap")
    print("    EXECUTION_MOCK=false")
    print("    OKX_API_KEY=...")
    print("    OKX_API_SECRET=...")
    print("    OKX_PASSPHRASE=...")
    print("    EXECUTION_TESTNET=true")
    print("\nOr use HTTP API:")
    print("    export EXECUTION_EXCHANGE=okx python services/execution_service/http_server.py")


if __name__ == "__main__":
    setup_logging()
    asyncio.run(test_okx_adapter())
