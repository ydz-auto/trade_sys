#!/usr/bin/env python3
"""
专门运行 short_squeeze 策略的 Walk-Forward 回测
2022 Optimization / 2023 Validation / 2024 Test
"""

import sys
import os
from datetime import datetime

# 添加项目路径
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
sys.path.insert(0, backend_path)

script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

from infrastructure.logging import get_logger
from run_all_30_strategies_v2 import WalkForwardRunner

logger = get_logger("short_squeeze_walkforward")

def main():
    print("="*80)
    print("Short Squeeze Pressure Strategy - Walk-Forward Backtest")
    print("="*80)
    
    # 初始化 WalkForwardRunner
    print(f"\n[{datetime.now()}] Initializing WalkForwardRunner...")
    runner = WalkForwardRunner(
        enable_gpu=True,
        resample="1h"  # 使用 1小时 K线
    )
    
    # 运行 Walk-Forward，只测试 short_squeeze 策略
    print(f"\n[{datetime.now()}] Running Walk-Forward for 'short_squeeze' strategy...")
    print("-"*80)
    print("Configuration:")
    print("  - Training Window: 2022")
    print("  - Validation Window: 2023")
    print("  - Testing Window: 2024")
    print("-"*80)
    
    result = runner.run_walk_forward(
        strategy_id="short_squeeze",
        optimize_year=2022,
        validation_year=2023,
        test_year=2024
    )
    results = [result] if result else []
    
    # 打印结果摘要
    print("\n" + "="*80)
    print("Walk-Forward Backtest Results - Short Squeeze Pressure")
    print("="*80)
    
    if not results:
        print("\n❌ No results found!")
        return 1
    
    for i, result in enumerate(results):
        print(f"\nResult {i+1}:")
        print(f"  Strategy: {result.strategy_id}")
        print(f"  Training Year: {result.optimize_year}")
        print(f"  Validation Year: {result.validation_year}")
        print(f"  Testing Year: {result.test_year}")
        print(f"  Best Params: {result.best_params}")
        print(f"  Optimization Sharpe: {result.optimize_sharpe:.2f}")
        print(f"  Validation Sharpe: {result.validation_sharpe:.2f}")
        print(f"  Testing Sharpe: {result.test_sharpe:.2f}")
        print(f"  Total Return (Test): {result.test_return:.2%}")
        print(f"  Max Drawdown (Test): {result.max_drawdown:.2%}")
        print(f"  Win Rate (Test): {result.win_rate:.2%}")
        print(f"  Profit Factor (Test): {result.profit_factor:.2f}")
        print(f"  Trade Count (Test): {result.test_trades}")
        print(f"  Overfitting Score: {result.overfitting_score:.2f}")
        
        # 评估结果
        test_sharpe = result.test_sharpe
        test_profit_factor = result.profit_factor
        test_trades = result.test_trades
        
        print("\n  Evaluation:")
        if test_sharpe > 1 and test_profit_factor > 1.2 and test_trades > 100:
            print("  ✅ GOOD - Trade-derived pressure proxy is effective!")
        elif test_sharpe > 0.5 and test_profit_factor > 1.1:
            print("  ⚠️ MEDIOCRE - May need additional features (funding, liquidation, regime)")
        else:
            print("  ❌ POOR - Need to add more features or revisit strategy logic")
    
    print("\n" + "="*80)
    print(f"[{datetime.now()}] Backtest complete!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
