"""
简单的多进程优化测试
"""
import sys
import os
import time

sys.path.insert(0, 'e:\\00_crypto\\00_code\\backend')
sys.path.insert(0, 'e:\\00_crypto\\00_code\\scripts')

from run_walkforward_fixed import WalkForwardRunner

def run_test():
    print("="*80)
    print("测试多进程参数优化")
    print("="*80)

    runner = WalkForwardRunner(enable_gpu=False, resample="1h")

    strategy_id = "long_liquidation_bounce"
    print(f"\n策略: {strategy_id}")

    param_grid = runner.generate_param_grid(strategy_id)
    print(f"参数组合数: {len(param_grid)}")

    optimize_bars = runner.load_year_data(2022)
    print(f"优化期数据: {len(optimize_bars)} bars")

    print("\n" + "-"*80)
    print("开始多进程参数优化...")
    print("-"*80)

    start_time = time.time()
    best_params, best_sharpe, best_trades, best_return = runner.optimize_params(
        strategy_id, optimize_bars, use_multiprocess=True
    )
    elapsed = time.time() - start_time

    print("\n" + "="*80)
    print("多进程优化结果")
    print("="*80)
    print(f"最佳参数: {best_params}")
    print(f"最佳Sharpe: {best_sharpe:.4f}")
    print(f"交易次数: {best_trades}")
    print(f"总收益: {best_return:.4f}")
    print(f"耗时: {elapsed:.2f}秒")
    print("="*80)

    print("\n" + "-"*80)
    print("对比串行模式...")
    print("-"*80)

    start_time = time.time()
    best_params_seq, best_sharpe_seq, best_trades_seq, best_return_seq = runner.optimize_params(
        strategy_id, optimize_bars, use_multiprocess=False
    )
    elapsed_seq = time.time() - start_time

    print("\n" + "="*80)
    print("串行优化结果")
    print("="*80)
    print(f"最佳Sharpe: {best_sharpe_seq:.4f}")
    print(f"耗时: {elapsed_seq:.2f}秒")
    print("="*80)

    print("\n" + "="*80)
    print("性能对比")
    print("="*80)
    print(f"多进程耗时: {elapsed:.2f}秒")
    print(f"串行耗时:   {elapsed_seq:.2f}秒")
    if elapsed > 0:
        print(f"加速比:     {elapsed_seq/elapsed:.2f}x")
    print("="*80)

if __name__ == '__main__':
    run_test()
