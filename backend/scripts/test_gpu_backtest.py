import pandas as pd
import time
import sys
import os
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.feature.unified_calculator import UnifiedFeatureCalculator
from application.optimization_service.engine import OptimizationBacktestEngine, BacktestConfig

KLINE_PATH = Path(r"E:\00_crypto\00_code\backend\data_lake\crypto\binance\klines\symbol=BTCUSDT\year=2023\month=04\data.parquet")

print("=" * 60)
print("Step 1: Load klines data (2023-04, 1 month)")
print("=" * 60)

df = pd.read_parquet(KLINE_PATH)
print(f"Shape: {df.shape}")
print(f"Columns: {list(df.columns)}")
print(f"Date range: {df['timestamp'].iloc[0]} ~ {df['timestamp'].iloc[-1]}")
print()

print("=" * 60)
print("Step 2: Feature extraction (GPU vs CPU)")
print("=" * 60)

calc_gpu = UnifiedFeatureCalculator(use_gpu=True)
print(f"GPU available: {calc_gpu._gpu_available}")

start = time.time()
result_gpu = calc_gpu.compute_batch(df, symbol="BTCUSDT", use_gpu=True)
gpu_elapsed = time.time() - start
print(f"GPU feature extraction: {gpu_elapsed:.2f}s ({len(result_gpu)} rows, {len(result_gpu.columns)} cols)")

calc_cpu = UnifiedFeatureCalculator(use_gpu=False)
start = time.time()
result_cpu = calc_cpu.compute_batch(df, symbol="BTCUSDT", use_gpu=False)
cpu_elapsed = time.time() - start
print(f"CPU feature extraction: {cpu_elapsed:.2f}s")

if cpu_elapsed > 0:
    speedup = cpu_elapsed / gpu_elapsed
    print(f"GPU speedup: {speedup:.1f}x")

feature_cols = [c for c in result_gpu.columns if c not in ["timestamp", "open", "high", "low", "close", "volume"]]
print(f"Features computed: {len(feature_cols)} ({feature_cols[:5]}...)")
print()

print("=" * 60)
print("Step 3: Run backtest (OptimizationBacktestEngine)")
print("=" * 60)

config = BacktestConfig()
engine = OptimizationBacktestEngine(config)
print(f"Engine GPU available: {engine._gpu_available}")

import asyncio

async def run_backtest():
    start_ts = int(datetime(2023, 4, 1).timestamp() * 1000)
    end_ts = int(datetime(2023, 4, 30, 23, 59).timestamp() * 1000)

    start = time.time()
    try:
        result = await engine.run(
            data_path=KLINE_PATH,
            symbol="BTCUSDT",
            strategy_id="sma_cross",
            params={"fast": 10, "slow": 50},
            start_time=start_ts,
            end_time=end_ts,
        )
        elapsed = time.time() - start
        print(f"Backtest elapsed: {elapsed:.2f}s")
        if hasattr(result, "to_dict"):
            d = result.to_dict()
            print(f"  Total trades: {d.get('total_trades', 0)}")
            print(f"  Win rate: {d.get('win_rate', 0):.2%}")
            print(f"  Total return: {d.get('total_return', 0):.2%}")
            print(f"  Max drawdown: {d.get('max_drawdown', 0):.2%}")
            print(f"  Sharpe ratio: {d.get('sharpe_ratio', 0):.4f}")
        else:
            print(f"  Result: {result}")
    except Exception as e:
        elapsed = time.time() - start
        print(f"Backtest error after {elapsed:.2f}s: {e}")
        import traceback
        traceback.print_exc()

asyncio.run(run_backtest())

print()
print("=" * 60)
print("Step 4: Parallel optimization (3x3 grid, asyncio.gather)")
print("=" * 60)

from application.optimization_service.service import OptimizationService
from application.optimization_service.models import OptimizationConfig

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
            "fast": [5, 10, 20],
            "slow": [30, 50, 100],
        },
        stop_loss=0.02,
        take_profit=0.04,
    )

    task = await service.create_task(
        strategy_id="sma_cross",
        symbol="BTCUSDT",
        config=config,
    )

    print(f"Task created: {task.task_id}")
    print(f"Total combos: {task.total_combos}")

    start = time.time()
    try:
        result = await service.run_task(task.task_id)
        elapsed = time.time() - start
        print(f"Optimization elapsed: {elapsed:.2f}s")
        print(f"Status: {result.status}")
        print(f"Best params: {result.best_params}")
        print(f"Best score: {result.best_score}")
        if result.all_results:
            print(f"Total results: {len(result.all_results)}")
            for r in result.all_results[:3]:
                print(f"  params={r.get('params')}, score={r.get('score', 0):.4f}")
    except Exception as e:
        elapsed = time.time() - start
        print(f"Optimization error after {elapsed:.2f}s: {e}")
        import traceback
        traceback.print_exc()

asyncio.run(run_optimization())
