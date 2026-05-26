#!/usr/bin/env python3
"""
Short Squeeze Smoke Test - 4 组参数快速验证
"""

import sys
import os
from datetime import datetime

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
sys.path.insert(0, backend_path)

script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

from infrastructure.logging import get_logger
from run_all_30_strategies_v2 import WalkForwardRunner, PARAM_GRIDS

logger = get_logger("smoke_test")

def main():
    print("="*80)
    print("Short Squeeze Smoke Test - 4 参数组合验证")
    print("="*80)
    
    # 使用小网格
    print("\n使用小网格参数:")
    print("  price_momentum_threshold: [0.003]")
    print("  cvd_zscore_threshold: [1.5, 2.0]")
    print("  taker_buy_ratio_threshold: [0.6]")
    print("  volume_zscore_threshold: [1.5, 2.0]")
    print("共 4 组参数组合\n")
    
    # 初始化 WalkForwardRunner
    print(f"[{datetime.now()}] Initializing...")
    runner = WalkForwardRunner(enable_gpu=True, resample="1h")
    
    # 临时替换参数网格
    original_grid = PARAM_GRIDS.get("short_squeeze", {})
    PARAM_GRIDS["short_squeeze"] = {
        "price_momentum_threshold": [0.003],
        "cvd_zscore_threshold": [1.5, 2.0],
        "taker_buy_ratio_threshold": [0.6],
        "volume_zscore_threshold": [1.5, 2.0],
    }
    
    print(f"[{datetime.now()}] Running Walk-Forward...")
    result = runner.run_walk_forward(
        strategy_id="short_squeeze",
        optimize_year=2022,
        validation_year=2023,
        test_year=2024
    )
    
    # 恢复原参数网格
    PARAM_GRIDS["short_squeeze"] = original_grid
    
    # 打印结果
    print("\n" + "="*80)
    print("Smoke Test Results")
    print("="*80)
    
    if result:
        print(f"\n✅ 策略运行成功！")
        print(f"  Strategy: {result.strategy_id}")
        print(f"  Best Params: {result.best_params}")
        print(f"  Optimization Sharpe: {result.optimize_sharpe:.2f}")
        print(f"  Validation Sharpe: {result.validation_sharpe:.2f}")
        print(f"  Testing Sharpe: {result.test_sharpe:.2f}")
        print(f"  Total Return (Test): {result.test_return:.2%}")
        print(f"  Max Drawdown (Test): {result.max_drawdown:.2%}")
        print(f"  Win Rate (Test): {result.win_rate:.2%}")
        print(f"  Profit Factor (Test): {result.profit_factor:.2f}")
        print(f"  Trade Count (Test): {result.test_trades}")
        
        # 验证关键指标
        print("\n验证检查:")
        if result.test_trades > 0:
            print(f"  ✅ 有交易: {result.test_trades} 笔")
        else:
            print(f"  ❌ 无交易!")
            
        if abs(result.test_return) < 100:
            print(f"  ✅ 收益正常: {result.test_return:.2%}")
        else:
            print(f"  ⚠️ 收益异常: {result.test_return:.2%}")
            
        if result.max_drawdown < 1:
            print(f"  ✅ 回撤正常: {result.max_drawdown:.2%}")
        else:
            print(f"  ⚠️ 回撤过大: {result.max_drawdown:.2%}")
            
        if result.profit_factor > 0:
            print(f"  ✅ Profit Factor: {result.profit_factor:.2f}")
        else:
            print(f"  ❌ Profit Factor 为负")
    else:
        print("\n❌ 策略运行失败!")
    
    print("\n" + "="*80)
    print(f"[{datetime.now()}] Smoke test 完成!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
