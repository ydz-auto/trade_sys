import os
os.environ['TORCH_DEVICE'] = 'cuda'

import sys
sys.path.insert(0, r'E:\00_crypto\00_code\backend')

import time
import asyncio
import gc

gc.collect()

from application.optimization_service.service import OptimizationService
from application.optimization_service.models import OptimizationConfig

print('=' * 60)
print('GPU Parallel Optimization Test')
print('=' * 60)

async def run_optimization():
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
            "fast": [5, 10],
            "slow": [30, 50],
        },
        stop_loss=0.02,
        take_profit=0.04,
        use_multiprocess=False,
    )

    task = await service.create_task(strategy_id="sma_cross", symbol="BTCUSDT", config=config)
    print(f"Task created: {task.task_id}")
    print(f"Total combos: {task.total_combos}")

    print("\nRunning optimization (asyncio, GPU)...")
    start = time.time()
    try:
        result = await service._run_task_sequential(task.task_id)
        elapsed = time.time() - start
        print(f"\nOptimization completed in {elapsed:.2f}s")
        print(f"Status: {result.status}")
        print(f"Best params: {result.best_params}")
        print(f"Best score: {result.best_score}")
    except Exception as e:
        elapsed = time.time() - start
        print(f"\nOptimization failed after {elapsed:.2f}s: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_optimization())
