#!/usr/bin/env python3
"""
测试架构优化后的 Walk-Forward 脚本
验证 27 组参数优化功能
"""
import sys
import os
import time
from pathlib import Path

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
sys.path.insert(0, backend_path)

from infrastructure.logging import get_logger
from runtimes.replay_runtime.backtest_engine import Bar
from scripts.run_walkforward_fixed import WalkForwardRunner

logger = get_logger("test_walkforward")


def test_single_year_optimization():
    """测试单年度参数优化 (27组参数)"""
    print("=" * 80)
    print("测试架构优化后的 Walk-Forward 脚本")
    print("=" * 80)
    print(f"Python executable: {sys.executable}")
    
    strategy_id = "long_liquidation_bounce"
    year = 2022
    
    logger.info(f"测试策略: {strategy_id}")
    logger.info(f"测试年份: {year}")
    logger.info("=" * 80)
    
    runner = WalkForwardRunner(enable_gpu=True, resample="1h")
    
    param_combinations = runner.generate_param_grid(strategy_id)
    logger.info(f"参数组合数: {len(param_combinations)}")
    logger.info(f"前 3 个参数: {param_combinations[:3]}")
    
    start_time = time.time()
    
    result = runner.run_single_year(year, strategy_id)
    
    elapsed = time.time() - start_time
    
    print("\n" + "=" * 80)
    print("优化结果")
    print("=" * 80)
    print(f"年份: {result.year}")
    print(f"最佳参数: {result.best_params}")
    print(f"训练集 Sharpe: {result.train_sharpe:.4f}")
    print(f"训练集交易次数: {result.train_trades}")
    print(f"验证集 Sharpe: {result.val_sharpe:.4f}")
    print(f"测试集 Sharpe: {result.test_sharpe:.4f}")
    print(f"衰退比率: {result.decay_ratio:.4f}")
    print(f"总耗时: {elapsed:.2f}秒")
    print("=" * 80)
    
    return result


def test_multiprocess_vs_sequential():
    """对比多进程和串行的性能"""
    print("\n" + "=" * 80)
    print("性能对比: 多进程 vs 串行")
    print("=" * 80)
    
    strategy_id = "long_liquidation_bounce"
    year = 2022
    
    runner = WalkForwardRunner(enable_gpu=False, resample="1h")
    
    bars = runner.load_year_data(year)
    param_combinations = runner.generate_param_grid(strategy_id)
    
    print(f"参数组合数: {len(param_combinations)}")
    print(f"数据条数: {len(bars)}")
    
    print("\n测试多进程模式:")
    start = time.time()
    best_params_mp, best_sharpe_mp, _, _ = runner.optimize_params(
        strategy_id, bars, use_multiprocess=True
    )
    time_mp = time.time() - start
    print(f"  耗时: {time_mp:.2f}秒")
    print(f"  最佳 Sharpe: {best_sharpe_mp:.4f}")
    print(f"  最佳参数: {best_params_mp}")
    
    print("\n测试串行模式:")
    start = time.time()
    best_params_seq, best_sharpe_seq, _, _ = runner.optimize_params(
        strategy_id, bars, use_multiprocess=False
    )
    time_seq = time.time() - start
    print(f"  耗时: {time_seq:.2f}秒")
    print(f"  最佳 Sharpe: {best_sharpe_seq:.4f}")
    print(f"  最佳参数: {best_params_seq}")
    
    print("\n" + "=" * 80)
    print("性能对比结果")
    print("=" * 80)
    if time_mp > 0:
        print(f"  加速比: {time_seq / time_mp:.2f}x")
    print(f"  结果一致: {best_params_mp == best_params_seq}")
    print(f"  Sharpe 一致: {abs(best_sharpe_mp - best_sharpe_seq) < 0.001}")
    print("=" * 80)


if __name__ == "__main__":
    try:
        print("开始测试...")
        test_single_year_optimization()
        test_multiprocess_vs_sequential()
        print("\n测试完成!")
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
