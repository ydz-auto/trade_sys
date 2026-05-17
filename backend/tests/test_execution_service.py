#!/usr/bin/env python3
"""
测试 Execution Service
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.execution_service import (
    ExecutionService,
    BinanceAdapter,
    OrderRequest,
    OrderSide,
    OrderType,
    Exchange,
    init_execution_service
)


async def test_execution_service():
    """测试执行服务"""
    print("=" * 70)
    print("测试 Execution Service")
    print("=" * 70)

    # 初始化
    service = await init_execution_service()

    print(f"\n已注册交易所: {[e.value for e in service._adapters.keys()]}")

    # 测试下单
    print("\n" + "=" * 70)
    print("测试下单")
    print("=" * 70)

    request = OrderRequest(
        symbol="BTC/USDT",
        exchange=Exchange.BINANCE,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.001
    )

    result = await service.execute_order(request)

    print(f"\n{'✅' if result.success else '❌'} 下单结果: {'成功' if result.success else '失败'}")

    if result.success and result.order:
        order = result.order
        print(f"\n  Order ID:      {order.order_id}")
        print(f"  Symbol:        {order.symbol}")
        print(f"  Side:          {order.side.value}")
        print(f"  Quantity:      {order.quantity}")
        print(f"  Price:         {order.average_price}")
        print(f"  Status:        {order.status.value}")

    # 测试获取持仓
    print("\n" + "=" * 70)
    print("测试获取持仓")
    print("=" * 70)

    positions = await service.get_all_positions()

    print(f"\n持仓数量: {len(positions)}")

    for pos in positions:
        print(f"\n  Symbol:   {pos.symbol}")
        print(f"  Quantity: {pos.quantity}")
        print(f"  Avg Cost: {pos.average_price}")
        print(f"  P&L:      {pos.unrealized_pnl}")

    # 测试获取余额
    print("\n" + "=" * 70)
    print("测试获取余额")
    print("=" * 70)

    balance = await service.get_balance(Exchange.BINANCE)

    for asset, amount in balance.items():
        print(f"\n  {asset}: {amount}")

    # 测试平仓
    print("\n" + "=" * 70)
    print("测试平仓")
    print("=" * 70)

    request = OrderRequest(
        symbol="BTC/USDT",
        exchange=Exchange.BINANCE,
        side=OrderSide.SELL,
        order_type=OrderType.MARKET,
        quantity=0.001
    )

    result = await service.execute_order(request)

    print(f"\n{'✅' if result.success else '❌'} 平仓结果: {'成功' if result.success else '失败'}")

    # 清理
    await service.disconnect_all()

    print("\n" + "=" * 70)
    print("✅ 测试完成！")
    print("=" * 70)

    print("\n使用说明:")
    print("""
要连接真实 Binance 账户:
1. 注册 Binance API
2. 设置环境变量:
   export BINANCE_API_KEY=your_api_key
   export BINANCE_API_SECRET=your_api_secret
   export BINANCE_TESTNET=false  # 使用主网

或使用测试网:
   export BINANCE_TESTNET=true  # 使用测试网（推荐先测试）
""")


if __name__ == "__main__":
    asyncio.run(test_execution_service())
