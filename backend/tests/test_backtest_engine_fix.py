#!/usr/bin/env python3
"""
测试修复后的回测引擎
验证杠杆、费用、强平、Sharpe 比率等功能
"""
import sys
sys.path.insert(0, '.')

from datetime import datetime, timedelta
import random
from runtime.replay_runtime.backtest_engine import (
    BacktestEngine, BacktestConfig, Bar, SignalType
)
from infrastructure.logging import get_logger

logger = get_logger("test_backtest_fix")


def generate_mock_bars(symbol, start_date, end_date, initial_price=50000, volatility=0.02):
    """生成模拟K线数据"""
    bars = []
    current_price = initial_price
    current_date = start_date
    
    while current_date <= end_date:
        # 生成随机价格变动
        change = random.gauss(0, volatility)
        open_price = current_price
        close_price = current_price * (1 + change)
        high_price = max(open_price, close_price) * (1 + abs(random.gauss(0, volatility/2)))
        low_price = min(open_price, close_price) * (1 - abs(random.gauss(0, volatility/2)))
        volume = random.uniform(100, 1000)
        
        bars.append(Bar(
            timestamp=current_date,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume
        ))
        
        current_price = close_price
        current_date += timedelta(minutes=60)  # 每小时一个K线
    
    return bars


def simple_strategy(bar, position):
    """简单的测试策略：随机买入"""
    if position:
        # 如果持仓，有20%概率卖出
        if random.random() < 0.05:
            return SignalType.SELL
        return SignalType.HOLD
    
    # 如果空仓，有3%概率买入
    if random.random() < 0.03:
        return SignalType.BUY
    
    return SignalType.HOLD


def test_basic_backtest():
    """测试基础回测功能"""
    print("\n" + "="*80)
    print("测试 1: 基础回测（无杠杆）")
    print("="*80)
    
    # 生成测试数据
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2024, 1, 31)
    bars = generate_mock_bars("BTC/USDT", start_date, end_date)
    
    # 配置回测（无杠杆）
    config = BacktestConfig(
        initial_capital=100000,
        leverage=1,
        position_size=0.1,
        stop_loss=0.05,
        take_profit=0.1,
        data_frequency_minutes=60
    )
    
    # 运行回测
    engine = BacktestEngine(config=config)
    engine.load_data(bars)
    result = engine.run(simple_strategy)
    
    engine.print_result(result)
    return result


def test_leverage_backtest():
    """测试带杠杆的回测"""
    print("\n" + "="*80)
    print("测试 2: 杠杆回测（10倍）")
    print("="*80)
    
    # 生成测试数据
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2024, 1, 31)
    bars = generate_mock_bars("BTC/USDT", start_date, end_date)
    
    # 配置回测（10倍杠杆）
    config = BacktestConfig(
        initial_capital=100000,
        leverage=10,
        position_size=0.1,
        stop_loss=0.1,
        take_profit=0.2,
        use_realistic_fees=True,
        maintenance_margin_rate=0.005,
        data_frequency_minutes=60
    )
    
    # 运行回测
    engine = BacktestEngine(config=config)
    engine.load_data(bars)
    result = engine.run(simple_strategy)
    
    engine.print_result(result)
    return result


def test_high_leverage_liquidation():
    """测试高杠杆强平"""
    print("\n" + "="*80)
    print("测试 3: 高杠杆强平测试（50倍）")
    print("="*80)
    
    # 生成测试数据（带剧烈波动）
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2024, 1, 7)
    bars = generate_mock_bars("BTC/USDT", start_date, end_date, volatility=0.05)
    
    # 配置回测（50倍杠杆，高风险）
    config = BacktestConfig(
        initial_capital=10000,
        leverage=50,
        position_size=0.2,  # 更大仓位
        stop_loss=0.2,
        take_profit=0.4,
        use_realistic_fees=True,
        maintenance_margin_rate=0.005,
        data_frequency_minutes=60
    )
    
    # 运行回测
    engine = BacktestEngine(config=config)
    engine.load_data(bars)
    result = engine.run(simple_strategy)
    
    engine.print_result(result)
    
    if result.metrics.liquidation_count > 0:
        print(f"\n✅ 强平测试成功！发生了 {result.metrics.liquidation_count} 次强平")
    else:
        print(f"\nℹ️ 未发生强平（数据波动可能不够大）")
    
    return result


def test_sharpe_ratio_calculation():
    """测试Sharpe比率计算"""
    print("\n" + "="*80)
    print("测试 4: Sharpe 比率计算验证")
    print("="*80)
    
    # 生成测试数据
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2024, 3, 31)  # 3个月数据
    bars = generate_mock_bars("BTC/USDT", start_date, end_date, volatility=0.01)
    
    # 测试不同频率
    for freq in [60, 5, 1]:  # 60分钟，5分钟，1分钟
        config = BacktestConfig(
            initial_capital=100000,
            leverage=1,
            position_size=0.05,
            stop_loss=0.05,
            take_profit=0.1,
            data_frequency_minutes=freq
        )
        
        engine = BacktestEngine(config=config)
        engine.load_data(bars)
        result = engine.run(simple_strategy)
        
        print(f"\n数据频率: {freq} 分钟")
        print(f"  夏普比率: {result.metrics.sharpe_ratio:.4f}")
        print(f"  交易次数: {result.metrics.total_trades}")
        print(f"  年化周期数: {(365*24*60)/freq:.0f}")


def main():
    """运行所有测试"""
    print("\n" + "="*80)
    print("🔧 开始测试修复后的回测引擎")
    print("="*80)
    
    random.seed(42)  # 设置随机种子以保证可复现
    
    # 运行测试
    result1 = test_basic_backtest()
    result2 = test_leverage_backtest()
    result3 = test_high_leverage_liquidation()
    test_sharpe_ratio_calculation()
    
    # 总结
    print("\n" + "="*80)
    print("📊 测试总结")
    print("="*80)
    print(f"测试 1 - 无杠杆: 收益 {result1.metrics.total_return_pct:.2%}, 夏普 {result1.metrics.sharpe_ratio:.2f}")
    print(f"测试 2 - 10倍杠杆: 收益 {result2.metrics.total_return_pct:.2%}, 夏普 {result2.metrics.sharpe_ratio:.2f}, 费用 ${result2.metrics.total_fees:.2f}")
    print(f"测试 3 - 50倍杠杆: 收益 {result3.metrics.total_return_pct:.2%}, 强平 {result3.metrics.liquidation_count} 次")
    
    print("\n✅ 所有测试完成！")


if __name__ == "__main__":
    main()
