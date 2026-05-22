import os
os.environ['TORCH_DEVICE'] = 'cpu'
os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ['CUDA_LAUNCH_BLOCKING'] = '1'

import sys
sys.path.insert(0, r'E:\00_crypto\00_code\backend')

import time
import asyncio
import gc

gc.collect()

from application.optimization_service.service import OptimizationService
from application.optimization_service.models import OptimizationConfig


async def run_sequential():
    service = OptimizationService()
    config = OptimizationConfig(
        initial_capital=10000,
        commission=0.0005,
        slippage=0.0002,
        position_size=0.3,
        optimization_start="2023-04-01",
        optimization_end="2023-04-30",
        method="grid_search",
        metric="sharpe_ratio",
        param_grid={
            "fast": [5, 10, 20],
            "slow": [30, 50],
        },
        stop_loss=0.02,
        take_profit=0.04,
        use_multiprocess=False,
    )

    task = await service.create_task(strategy_id="sma_cross", symbol="BTCUSDT", config=config)
    print(f"Sequential: 6 combos (2x3), 1 at a time")

    start = time.time()
    result = await service._run_task_sequential(task.task_id)
    elapsed = time.time() - start
    return elapsed, result


async def run_parallel_multiprocess():
    service = OptimizationService()
    config = OptimizationConfig(
        initial_capital=10000,
        commission=0.0005,
        slippage=0.0002,
        position_size=0.3,
        optimization_start="2023-04-01",
        optimization_end="2023-04-30",
        method="grid_search",
        metric="sharpe_ratio",
        param_grid={
            "fast": [5, 10, 20],
            "slow": [30, 50],
        },
        stop_loss=0.02,
        take_profit=0.04,
        use_multiprocess=True,
    )

    task = await service.create_task(strategy_id="sma_cross", symbol="BTCUSDT", config=config)
    print(f"Parallel (multiprocess): 6 combos (2x3), 3 workers (ProcessPoolExecutor)")

    start = time.time()
    result = await service.run_task(task.task_id)
    elapsed = time.time() - start
    return elapsed, result


if __name__ == "__main__":
    print("=" * 60)
    print("Comparison: Sequential vs Multiprocess Parallel")
    print("(2x3 grid = 6 combinations, CPU mode)")
    print("=" * 60)

    print()
    print("--- Sequential (baseline) ---")
    seq_elapsed, seq_result = asyncio.run(run_sequential())
    print(f"Sequential elapsed: {seq_elapsed:.2f}s")
    if seq_result:
        print(f"  Status: {seq_result.status}")
        print(f"  Best score: {seq_result.best_score}")
        print(f"  Best params: {seq_result.best_params}")

    print()
    print("--- Parallel (ProcessPoolExecutor - true multiprocess) ---")
    par_elapsed, par_result = asyncio.run(run_parallel_multiprocess())
    print(f"Parallel elapsed: {par_elapsed:.2f}s")
    if par_result:
        print(f"  Status: {par_result.status}")
        print(f"  Best score: {par_result.best_score}")
        print(f"  Best params: {par_result.best_params}")

    print()
    print("=" * 60)
    if seq_elapsed > 0 and par_elapsed > 0:
        speedup = seq_elapsed / par_elapsed
        print(f"Speedup: {speedup:.2f}x")
        print(f"Time saved: {seq_elapsed - par_elapsed:.2f}s ({par_elapsed/seq_elapsed*100:.1f}% of original time)")
    print("=" * 60)
