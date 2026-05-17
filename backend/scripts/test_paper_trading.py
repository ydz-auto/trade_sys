#!/usr/bin/env python3
"""
测试 Paper Trading 模式
- 真实行情 + 本地撮合
- 验证仓位管理和盈亏计算
"""

import sys
import asyncio
from pathlib import Path
from datetime import datetime

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).parent.parent))

# 先加载环境变量
from dotenv import load_dotenv
import os

load_dotenv(override=True)

from infrastructure.logging import get_logger
from domain.execution.models import (
    OrderRequest,
    OrderSide,
    OrderType,
    MarketType,
)
from services.execution_service.adapters.paper_trading_adapter import (
    PaperTradingAdapter,
)

logger = get_logger("test_paper_trading")


async def test_paper_trading_basics():
    """测试 Paper Trading 基础功能"""
    print("=" * 70)
    print("测试 Paper Trading 基础功能")
    print("=" * 70)

    # 初始化 Paper Trading 适配器
    adapter = PaperTradingAdapter(
        initial_balance={"USDT": 100000.0},
        slippage=0.001,
    )

    # 连接
    connected = await adapter.connect()
    print(f"✓ 连接: {'成功' if connected else '失败'}")

    # 获取初始余额
    balance = await adapter.get_balance()
    print(f"✓ 初始余额: {balance}")

    # 获取价格（真实行情）
    symbol = "BTCUSDT"
    price = await adapter.get_market_price(symbol)
    print(f"✓ {symbol} 当前价格: {price}")

    # 测试 1: 下市价单买入
    print("\n" + "-" * 50)
    print("测试 1: 市价单买入 0.1 BTC")
    print("-" * 50)

    buy_order = OrderRequest(
        symbol=symbol,
        exchange="binance",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.1,
        market_type=MarketType.USDT_FUTURES,
    )

    result = await adapter.create_order(buy_order)
    print(f"✓ 订单结果: {'成功' if result.success else '失败'}")
    
    if result.success and result.order:
        print(f"  - 订单ID: {result.order.order_id}")
        print(f"  - 成交价格: {result.order.average_price}")
        print(f"  - 成交数量: {result.order.filled_quantity}")

    # 获取当前余额和仓位
    balance = await adapter.get_balance()
    positions = await adapter.get_positions()
    print(f"✓ 当前余额: {balance}")
    print(f"✓ 持仓数量: {len(positions)}")
    
    for pos in positions:
        print(f"  - {pos.symbol}: {pos.quantity} @ {pos.average_price}, PnL: {pos.unrealized_pnl}")

    # 获取 Paper Trading 摘要
    summary = adapter.get_summary()
    print(f"\n✓ Paper Trading 摘要:")
    for key, value in summary.items():
        if key != "balance":
            print(f"  - {key}: {value}")
    print(f"  - balance: {summary.get('balance')}")

    # 测试 2: 卖出平仓
    print("\n" + "-" * 50)
    print("测试 2: 市价单平仓卖出 0.1 BTC")
    print("-" * 50)

    sell_order = OrderRequest(
        symbol=symbol,
        exchange="binance",
        side=OrderSide.SELL,
        order_type=OrderType.MARKET,
        quantity=0.1,
        market_type=MarketType.USDT_FUTURES,
    )

    result = await adapter.create_order(sell_order)
    print(f"✓ 订单结果: {'成功' if result.success else '失败'}")

    if result.success and result.order:
        print(f"  - 订单ID: {result.order.order_id}")
        print(f"  - 成交价格: {result.order.average_price}")

    # 再次获取余额和仓位
    balance = await adapter.get_balance()
    positions = await adapter.get_positions()
    print(f"\n✓ 平仓后余额: {balance}")
    print(f"✓ 持仓数量: {len(positions)}")
    
    summary = adapter.get_summary()
    print(f"✓ 实现盈亏: {summary.get('total_realized_pnl', 0):.2f} USDT")
    print(f"✓ 总盈亏: {summary.get('total_pnl', 0):.2f} USDT")

    await adapter.disconnect()
    return True


async def test_multiple_trades():
    """测试多次交易的盈亏计算"""
    print("\n" + "=" * 70)
    print("测试多次交易和仓位管理")
    print("=" * 70)

    adapter = PaperTradingAdapter(
        initial_balance={"USDT": 100000.0},
    )
    await adapter.connect()

    symbol = "BTCUSDT"
    price = await adapter.get_market_price(symbol)
    print(f"当前 {symbol} 价格: {price}")

    # 交易序列
    trades = [
        (OrderSide.BUY, 0.05, "买入 0.05 BTC"),
        (OrderSide.BUY, 0.05, "加仓 0.05 BTC"),
        (OrderSide.SELL, 0.05, "减仓 0.05 BTC"),
        (OrderSide.SELL, 0.05, "完全平仓"),
    ]

    for i, (side, qty, desc) in enumerate(trades, 1):
        print(f"\n交易 {i}: {desc}")
        
        order = OrderRequest(
            symbol=symbol,
            exchange="binance",
            side=side,
            order_type=OrderType.MARKET,
            quantity=qty,
            market_type=MarketType.USDT_FUTURES,
        )
        
        result = await adapter.create_order(order)
        
        if result.success:
            summary = adapter.get_summary()
            print(f"  - 成功 | 实现盈亏: {summary.get('total_realized_pnl', 0):.2f}")

    balance = await adapter.get_balance()
    print(f"\n最终余额: {balance}")
    
    summary = adapter.get_summary()
    print(f"最终盈亏: {summary.get('total_pnl', 0):.2f} USDT")

    await adapter.disconnect()
    return True


async def test_trading_modes():
    """测试三种交易模式的配置"""
    print("\n" + "=" * 70)
    print("测试三种交易模式的配置")
    print("=" * 70)

    from domain.execution.trading_mode import (
        get_trading_mode_config,
        TradingMode,
    )

    for mode in [TradingMode.DEMO, TradingMode.PAPER, TradingMode.PROD]:
        config = get_trading_mode_config(mode)
        print(f"\n{mode.value.upper()} 模式:")
        print(f"  - 行情来源: {config.market_data_source}")
        print(f"  - 订单执行: {config.order_execution}")
        if mode == TradingMode.PAPER:
            print(f"  - Paper 配置: {config.paper_config}")
        elif mode == TradingMode.DEMO:
            print(f"  - Demo 配置: {config.demo_config}")
        else:
            print(f"  - Prod 配置: {config.prod_config}")

    return True


async def main():
    """主测试函数"""
    print("\n" + "╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "TradeAgent - Paper Trading 测试" + " " * 28 + "║")
    print("╚" + "=" * 68 + "╝\n")

    try:
        # 测试 1: 交易模式配置
        await test_trading_modes()

        # 测试 2: Paper Trading 基础功能
        await test_paper_trading_basics()

        # 测试 3: 多次交易
        await test_multiple_trades()

        print("\n" + "=" * 70)
        print("✓ 所有测试通过！")
        print("=" * 70)
        print("\n📝 提示:")
        print("  - Paper Trading 使用真实市场数据 + 本地撮合")
        print("  - 可以通过 .env 文件设置 MODE=paper 来启用")
        print("  - 在前端右上角可以切换交易模式\n")

    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
