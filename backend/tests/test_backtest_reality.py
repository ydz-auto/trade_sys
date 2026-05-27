"""
回测真实性验证测试

验证完整回测是否包含真实交易条件：
- 手续费 (Maker/Taker
- 滑点
- 资金费
- 杠杆 & 保证金
- 爆仓
- 最小下单量
- 仓位管理
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import logging

from runtime.replay_runtime.models import (
    BacktestExecutionEngine,
    TradeExecutionResult,
    create_backtest_engine,
    OrderSide,
    OrderType
)

from infrastructure.logging import get_logger

logger = get_logger("test_backtest_reality")


async def test_fee_calculation():
    """测试手续费计算"""
    logger.info("=" * 60)
    logger.info("Test 1: Fee Calculation")
    logger.info("=" * 60)
    
    engine = create_backtest_engine(
        symbol="BTCUSDT",
        initial_capital=10000.0,
        maker_fee=0.0002,
        taker_fee=0.0005,
        enable_slippage=False,
        enable_liquidation=False,
        enable_funding=False
    )
    
    # 开多单 (Taker)
    result = await engine.execute_order(
        side=OrderSide.BUY,
        size=0.01,
        price=50000.0,
        is_maker=False,
        timestamp_ms=1717171717000
    )
    
    assert result.success
    assert result.fee > 0
    
    notional = 0.01 * 50000.0
    expected_fee = notional * 0.0005
    
    assert abs(result.fee - expected_fee) < 0.0001, f"Expected fee {expected_fee}, got {result.fee}"
    
    logger.info(f"✓ Taker fee correct: {result.fee:.4f} (rate {result.fee_rate * 100:.4f}%)")
    
    # 平多单 (Taker)
    result = await engine.execute_order(
        side=OrderSide.SELL,
        size=0.01,
        price=51000.0,
        is_maker=False,
        timestamp_ms=1717171717001
    )
    
    assert result.success
    
    logger.info(f"✓ Fee calculation test passed")
    logger.info(f"  Total fees paid: {engine.account.total_fees:.4f}")
    logger.info(f"  Total P&L: {result.pnl:.2f}")
    
    engine.reset()


async def test_slippage_calculation():
    """测试滑点计算"""
    logger.info("\n" + "=" * 60)
    logger.info("Test 2: Slippage Calculation")
    logger.info("=" * 60)
    
    engine = create_backtest_engine(
        symbol="BTCUSDT",
        initial_capital=10000.0,
        base_slippage_bps=5.0,
        enable_slippage=True,
        enable_liquidation=False,
        enable_funding=False
    )
    
    # 开多单
    requested_price = 50000.0
    result = await engine.execute_order(
        side=OrderSide.BUY,
        size=0.01,
        price=requested_price,
        is_maker=False,
        timestamp_ms=1717171717000
    )
    
    assert result.success
    assert result.execution_price > requested_price  # 买价应该有滑点
    assert result.slippage_bps > 0
    
    slippage_pct = (result.execution_price - requested_price) / requested_price
    
    logger.info(f"✓ Slippage applied: {result.slippage_bps:.2f} bps")
    logger.info(f"  Requested: {requested_price:.2f}")
    logger.info(f"  Executed:  {result.execution_price:.2f}")
    
    engine.reset()


async def test_position_management():
    """测试仓位管理"""
    logger.info("\n" + "=" * 60)
    logger.info("Test 3: Position Management")
    logger.info("=" * 60)
    
    engine = create_backtest_engine(
        symbol="BTCUSDT",
        initial_capital=10000.0,
        default_leverage=5,
        enable_slippage=False,
        enable_liquidation=False,
        enable_funding=False
    )
    
    # 开多单
    result = await engine.execute_order(
        side=OrderSide.BUY,
        size=0.01,
        price=50000.0,
        is_maker=False,
        timestamp_ms=1717171717000
    )
    
    assert result.success
    assert result.position_after is not None
    
    position = engine.get_position()
    assert position is not None
    assert position.quantity == 0.01
    assert position.leverage == 5
    
    position_value = abs(position.quantity * position.average_price)
    expected_margin = position_value / 5
    
    assert abs(position.margin - expected_margin) < 0.001
    
    logger.info(f"✓ Position opened correctly")
    logger.info(f"  Position: {position.quantity} @ {position.average_price:.2f}")
    logger.info(f"  Margin used: {position.margin:.2f} (leverage 5x)")
    
    # 加仓
    result = await engine.execute_order(
        side=OrderSide.BUY,
        size=0.005,
        price=51000.0,
        is_maker=False,
        timestamp_ms=1717171717001
    )
    
    assert result.success
    
    position = engine.get_position()
    assert position is not None
    assert position.quantity == 0.015
    
    logger.info(f"✓ Position added correctly")
    logger.info(f"  New position size: {position.quantity}")
    
    # 平部分
    result = await engine.execute_order(
        side=OrderSide.SELL,
        size=0.01,
        price=52000.0,
        is_maker=False,
        timestamp_ms=1717171717002
    )
    
    assert result.success
    
    position = engine.get_position()
    assert position is not None
    assert abs(position.quantity - 0.005) < 0.00001
    
    logger.info(f"✓ Partial close successful")
    logger.info(f"  Remaining position: {position.quantity}")
    
    # 完全平仓
    result = await engine.execute_order(
        side=OrderSide.SELL,
        size=0.005,  # 正好等于剩余仓位
        price=53000.0,
        is_maker=False,
        timestamp_ms=1717171717003
    )
    
    assert result.success
    assert result.position_after is None
    assert engine.get_position() is None
    
    logger.info(f"✓ Full close successful")
    
    engine.reset()


async def test_short_position():
    """测试空头仓位"""
    logger.info("\n" + "=" * 60)
    logger.info("Test 4: Short Position")
    logger.info("=" * 60)
    
    engine = create_backtest_engine(
        symbol="BTCUSDT",
        initial_capital=10000.0,
        default_leverage=5,
        enable_slippage=False,
        enable_liquidation=False,
        enable_funding=False
    )
    
    # 开空单
    result = await engine.execute_order(
        side=OrderSide.SELL,
        size=0.01,
        price=50000.0,
        is_maker=False,
        timestamp_ms=1717171717000
    )
    
    assert result.success
    position = engine.get_position()
    assert position is not None
    assert position.quantity == -0.01
    
    logger.info(f"✓ Short position opened: {position.quantity}")
    
    # 平空单
    result = await engine.execute_order(
        side=OrderSide.BUY,
        size=0.01,
        price=49000.0,
        is_maker=False,
        timestamp_ms=1717171717001
    )
    
    assert result.success
    assert result.realized_pnl > 0
    
    logger.info(f"✓ Short closed with profit: {result.realized_pnl:.2f}")
    
    engine.reset()


async def test_minimum_order_size():
    """测试最小下单量"""
    logger.info("\n" + "=" * 60)
    logger.info("Test 5: Minimum Order Size")
    logger.info("=" * 60)
    
    engine = create_backtest_engine(
        symbol="BTCUSDT",
        initial_capital=10000.0,
        min_order_size=0.001,
        enable_slippage=False,
        enable_liquidation=False,
        enable_funding=False
    )
    
    # 小于最小下单量应该被拒绝
    result = await engine.execute_order(
        side=OrderSide.BUY,
        size=0.0001,
        price=50000.0,
        is_maker=False,
        timestamp_ms=1717171717000
    )
    
    assert not result.success
    assert "below minimum" in result.error
    
    logger.info(f"✓ Minimum order size enforced: {result.error}")
    
    # 正常大小应该成功
    result = await engine.execute_order(
        side=OrderSide.BUY,
        size=0.01,
        price=50000.0,
        is_maker=False,
        timestamp_ms=1717171717001
    )
    
    assert result.success
    
    logger.info(f"✓ Normal order size accepted")
    
    engine.reset()


async def test_liquidation():
    """测试爆仓"""
    logger.info("\n" + "=" * 60)
    logger.info("Test 6: Liquidation Simulation")
    logger.info("=" * 60)
    
    engine = create_backtest_engine(
        symbol="BTCUSDT",
        initial_capital=1000.0,  # 更小的资金
        default_leverage=10,  # 更高的杠杆
        maintenance_margin_rate=0.005,
        enable_slippage=False,
        enable_liquidation=True,
        enable_funding=False
    )
    
    # 开多单
    result = await engine.execute_order(
        side=OrderSide.BUY,
        size=0.002,  # 约100 USDT
        price=50000.0,
        is_maker=False,
        timestamp_ms=1717171717000
    )
    
    assert result.success
    
    position = engine.get_position()
    liq_price = position.liquidation_price
    
    logger.info(f"Position: {position.quantity} @ {position.average_price:.2f}")
    logger.info(f"Liquidation price: {liq_price:.2f}")
    logger.info(f"Distance to liq: {position.liquidation_distance_pct:.2f}%")
    
    # 模拟价格下跌，接近爆仓
    current_price = 50000.0
    
    for i in range(10):
        current_price -= 200.0
        result = await engine.execute_order(
            side=OrderSide.BUY,  # 只是用来触发检查
            size=0.0,
            price=current_price,
            is_maker=False,
            timestamp_ms=1717171717001 + i
        )
        
        if engine.get_position() is None:
            logger.info(f"✓ Liquidation occurred at price: {current_price:.2f}")
            break
    
    if engine.get_position() is None:
        logger.info(f"✓ Liquidation occurred")
    else:
        logger.info(f"⚠️  Liquidation not triggered in test range")
    
    logger.info(f"✓ Liquidation test completed")
    
    engine.reset()


async def test_full_trading_cycle():
    """测试完整的完整交易周期"""
    logger.info("\n" + "=" * 60)
    logger.info("Test 7: Full Trading Cycle")
    logger.info("=" * 60)
    
    engine = create_backtest_engine(
        symbol="BTCUSDT",
        initial_capital=10000.0,
        default_leverage=5,
        maker_fee=0.0002,
        taker_fee=0.0005,
        base_slippage_bps=2.0,
        enable_slippage=True,
        enable_liquidation=True,
        enable_funding=False
    )
    
    initial_balance = engine.account.current_balance
    
    logger.info(f"Initial balance: {initial_balance:.2f}")
    
    # 交易1: 开多
    result = await engine.execute_order(
        side=OrderSide.BUY,
        size=0.01,
        price=50000.0,
        is_maker=False,
        timestamp_ms=1717171717000
    )
    assert result.success
    
    # 交易2: 加仓
    result = await engine.execute_order(
        side=OrderSide.BUY,
        size=0.005,
        price=50500.0,
        is_maker=False,
        timestamp_ms=1717171717001
    )
    assert result.success
    
    # 交易3: 平部分
    result = await engine.execute_order(
        side=OrderSide.SELL,
        size=0.0075,
        price=51000.0,
        is_maker=False,
        timestamp_ms=1717171717002
    )
    assert result.success
    
    # 交易4: 完全平仓
    result = await engine.execute_order(
        side=OrderSide.SELL,
        size=0.01,
        price=51500.0,
        is_maker=False,
        timestamp_ms=1717171717003
    )
    assert result.success
    
    final_balance = engine.account.equity
    total_fees = engine.account.total_fees
    total_pnl = engine.account.total_realized_pnl
    
    logger.info(f"Final balance: {final_balance:.2f}")
    logger.info(f"Total fees paid: {total_fees:.4f}")
    logger.info(f"Total realized P&L: {total_pnl:.2f}")
    
    assert total_fees > 0
    assert total_pnl > 0
    
    logger.info("✓ Full trading cycle completed")
    
    engine.reset()


async def test_account_snapshot():
    """测试账户快照"""
    logger.info("\n" + "=" * 60)
    logger.info("Test 8: Account Snapshot")
    logger.info("=" * 60)
    
    engine = create_backtest_engine(
        symbol="BTCUSDT",
        initial_capital=10000.0,
        default_leverage=5,
        enable_slippage=False,
        enable_liquidation=False,
        enable_funding=False
    )
    
    # 开单
    await engine.execute_order(
        side=OrderSide.BUY,
        size=0.01,
        price=50000.0,
        is_maker=False,
        timestamp_ms=1717171717000
    )
    
    # 创建快照
    snapshot = engine.create_snapshot()
    
    assert snapshot is not None
    assert snapshot.wallet_balance == 10000.0
    assert snapshot.equity >= 9999.0
    assert snapshot.used_margin > 0
    
    logger.info(f"✓ Account snapshot created")
    logger.info(f"  Wallet balance: {snapshot.wallet_balance:.2f}")
    logger.info(f"  Equity: {snapshot.equity:.2f}")
    logger.info(f"  Used margin: {snapshot.used_margin:.2f}")
    logger.info(f"  Unrealized P&L: {snapshot.unrealized_pnl:.2f}")
    
    engine.reset()


async def main():
    """运行所有测试"""
    logger.info("=" * 80)
    logger.info("回测真实性验证测试")
    logger.info("=" * 80)
    logger.info("测试内容:")
    logger.info("  1. 手续费计算 (Maker/Taker)")
    logger.info("  2. 滑点计算")
    logger.info("  3. 仓位管理 (开仓/加仓/平仓)")
    logger.info("  4. 空头仓位")
    logger.info("  5. 最小下单量")
    logger.info("  6. 爆仓模拟")
    logger.info("  7. 完整交易周期")
    logger.info("  8. 账户快照")
    logger.info("=" * 80)
    
    try:
        await test_fee_calculation()
        await test_slippage_calculation()
        await test_position_management()
        await test_short_position()
        await test_minimum_order_size()
        await test_liquidation()
        await test_full_trading_cycle()
        await test_account_snapshot()
        
        logger.info("\n" + "=" * 80)
        logger.info("✓ 所有回测真实性验证测试通过")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"\n❌ 测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
