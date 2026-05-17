#!/usr/bin/env python3
"""
测试 Backtest Service
"""

import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.backtest_service import (
    BacktestEngine,
    BacktestConfig,
    Bar,
    SignalType
)


def example_rsi_strategy(bar: Bar, position: dict) -> SignalType:
    """RSI 策略示例"""
    # 简化 RSI 策略
    # 实际应该使用历史数据计算 RSI
    # 这里简化处理
    if position:
        return SignalType.HOLD

    # 模拟 RSI < 30 超卖买入
    # RSI > 70 超买卖出
    import random
    rsi = random.uniform(20, 80)

    if rsi < 30:
        return SignalType.BUY

    return SignalType.HOLD


def example_ma_cross_strategy(bar: Bar, position: dict) -> SignalType:
    """移动平均线交叉策略示例"""
    if position:
        return SignalType.HOLD

    # 模拟金叉/死叉
    import random
    if random.random() > 0.95:  # 5% 概率买入
        return SignalType.BUY

    return SignalType.HOLD


def test_backtest():
    """测试回测服务"""
    print("=" * 70)
    print("测试 Backtest Service")
    print("=" * 70)

    # 配置
    config = BacktestConfig(
        initial_capital=100000.0,
        commission=0.001,
        slippage=0.0005,
        position_size=0.1,
        stop_loss=0.02,
        take_profit=0.05
    )

    print("\n📊 回测配置:")
    print(f"   初始资金: ${config.initial_capital:,.2f}")
    print(f"   手续费: {config.commission:.2%}")
    print(f"   滑点: {config.slippage:.2%}")
    print(f"   仓位: {config.position_size:.0%}")
    print(f"   止损: {config.stop_loss:.0%}")
    print(f"   止盈: {config.take_profit:.0%}")

    # 创建引擎
    engine = BacktestEngine(config)

    # 加载模拟数据
    print("\n" + "=" * 70)
    print("加载模拟数据...")
    print("=" * 70)

    engine.load_mock_data(
        symbol="BTC/USDT",
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 3, 31),
        initial_price=50000.0
    )

    print(f"   加载 K线数: {len(engine._bars)}")
    print(f"   时间范围: {engine._bars[0].timestamp.date()} ~ {engine._bars[-1].timestamp.date()}")

    # 运行回测
    print("\n" + "=" * 70)
    print("运行回测...")
    print("=" * 70)

    print("\n策略1: MA 交叉策略")
    result = engine.run(example_ma_cross_strategy)
    engine.print_result(result)

    print("\n策略2: RSI 策略")
    result2 = engine.run(example_rsi_strategy)
    engine.print_result(result2)

    # 对比
    print("\n" + "=" * 70)
    print("📊 策略对比")
    print("=" * 70)
    print(f"\n{'指标':<20} {'MA 交叉':<15} {'RSI 策略':<15}")
    print("-" * 50)
    print(f"{'总收益':<20} {result.metrics.total_return:>+.2f}       {result2.metrics.total_return:>+.2f}")
    print(f"{'收益率':<20} {result.metrics.total_return_pct:>+.2%}       {result2.metrics.total_return_pct:>+.2%}")
    print(f"{'夏普比率':<20} {result.metrics.sharpe_ratio:>10.2f}       {result2.metrics.sharpe_ratio:>10.2f}")
    print(f"{'最大回撤':<20} {result.metrics.max_drawdown_pct:>+.2%}       {result2.metrics.max_drawdown_pct:>+.2%}")
    print(f"{'胜率':<20} {result.metrics.win_rate:>10.2%}       {result2.metrics.win_rate:>10.2%}")
    print(f"{'交易次数':<20} {result.metrics.total_trades:>10}       {result2.metrics.total_trades:>10}")

    print("\n" + "=" * 70)
    print("✅ 测试完成！")
    print("=" * 70)

    print("\n使用说明:")
    print("""
回测服务支持：
1. 历史数据回放
2. 策略回测评估
3. 绩效指标计算
4. 多策略对比

集成到系统：
1. 从数据库加载历史 K 线数据
2. 编写自定义策略函数
3. 运行回测获取结果
4. 根据结果优化策略
""")


if __name__ == "__main__":
    test_backtest()
