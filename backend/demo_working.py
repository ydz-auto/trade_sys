#!/usr/bin/env python3
"""
能跑通的Alpha回测 - 使用正确的API
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from services.backtest_service import (
    BacktestEngine,
    BacktestConfig,
    SignalType,
    Bar,
    MockDataGenerator
)


def simple_strategy(bar, position):
    """简单策略演示"""
    if bar.close > 52000 and not position:
        return SignalType.BUY
    elif bar.close < 48000 and position:
        return SignalType.SELL
    return SignalType.HOLD


def main():
    print("\n" + "="*80)
    print("  🚀 Alpha 回测系统演示")
    print("="*80)
    
    # 1. 配置
    print("\n[1/4] 配置回测...")
    config = BacktestConfig(
        initial_capital=100000,
        commission=0.001,
        slippage=0.001
    )
    engine = BacktestEngine(config)
    
    # 2. 加载数据
    print("\n[2/4] 加载模拟数据...")
    start_date = datetime.now() - timedelta(days=100)
    end_date = datetime.now()
    engine.load_mock_data("BTC/USDT", start_date, end_date, 50000.0)
    
    # 3. 运行回测
    print("\n[3/4] 运行策略...")
    result = engine.run(simple_strategy)
    
    # 4. 打印结果
    print("\n[4/4] 回测结果:")
    print("="*80)
    print(f"总收益: {result.metrics.total_return_pct:.2%}")
    print(f"夏普比率: {result.metrics.sharpe_ratio:.2f}")
    print(f"最大回撤: {result.metrics.max_drawdown_pct:.2%}")
    print(f"交易次数: {result.metrics.total_trades}")
    print(f"胜率: {result.metrics.win_rate:.2%}")
    print(f"盈亏比: {result.metrics.profit_factor:.2f}")
    
    print("\n" + "="*80)
    print("  ✅ 回测系统正常运行！")
    print("="*80)
    print("\n现在可以:")
    print("  - 实现因子策略（RSI, MACD等）")
    print("  - 接入 Data Lake 真实数据")
    print("  - 使用 Walk-Forward 滚动回测")
    print("  - 用 Experiment Tracker 追踪实验")


if __name__ == "__main__":
    main()

