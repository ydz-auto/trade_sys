"""
测试系统层 GridSearchOptimizer

验证架构分层后的参数优化能力
"""
import sys
import os
import time
from pathlib import Path

backend_path = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, backend_path)

sys.path.insert(0, str(Path(backend_path).parent))

from infrastructure.storage.parquet_reader import read_parquet_safe
from engines.optimization import ParallelExecutor, GridSearchOptimizer


def load_bars_data(year=2022):
    """加载测试数据"""
    data_path = Path(backend_path) / "data_lake" / "crypto" / "binance" / "klines" / "symbol=BTCUSDT" / f"year={year}"
    
    bars = []
    if data_path.exists():
        for month_dir in sorted(data_path.iterdir()):
            if month_dir.is_dir() and month_dir.name.startswith("month="):
                parquet_file = month_dir / "data.parquet"
                if parquet_file.exists():
                    df = read_parquet_safe(parquet_file)
                    if df is not None and len(df) > 0:
                        for _, row in df.iterrows():
                            try:
                                import pandas as pd
                                ts = pd.to_datetime(row['timestamp']).tz_localize('UTC')
                                bars.append({
                                    "timestamp": ts,
                                    "open": float(row.get('open', 0)),
                                    "high": float(row.get('high', 0)),
                                    "low": float(row.get('low', 0)),
                                    "close": float(row.get('close', 0)),
                                    "volume": float(row.get('volume', 0)),
                                })
                            except:
                                continue
    
    return bars


def test_grid_search_multiprocess():
    """测试多进程优化"""
    print("="*80)
    print("测试 GridSearchOptimizer (多进程)")
    print("="*80)
    
    bars_data = load_bars_data(2022)
    print(f"加载数据: {len(bars_data)} bars")
    
    optimizer = GridSearchOptimizer(
        executor=ParallelExecutor(executor_type="process", max_workers=15)
    )
    
    param_grid = {
        "drop_threshold": [-0.015, -0.02],
        "rsi_threshold": [20, 25],
        "volume_ratio_threshold": [1.5, 2.0]
    }
    
    print(f"参数组合数: {2 * 2 * 2} = 8")
    
    print("\n开始优化...")
    start_time = time.time()
    result = optimizer.optimize(
        strategy_id="long_liquidation_bounce",
        param_grid=param_grid,
        bars_data=bars_data,
        verbose=True
    )
    elapsed = time.time() - start_time
    
    print(f"\n优化完成!")
    print(f"最佳参数: {result['best_params']}")
    print(f"最佳Sharpe: {result['best_score']:.4f}")
    print(f"耗时: {elapsed:.2f}秒")
    
    return elapsed


def test_grid_search_sequential():
    """测试串行优化"""
    print("\n" + "="*80)
    print("测试 GridSearchOptimizer (串行)")
    print("="*80)
    
    bars_data = load_bars_data(2022)
    
    optimizer = GridSearchOptimizer(
        executor=ParallelExecutor(executor_type="sequential", max_workers=1)
    )
    
    param_grid = {
        "drop_threshold": [-0.015, -0.02],
        "rsi_threshold": [20, 25],
        "volume_ratio_threshold": [1.5, 2.0]
    }
    
    print(f"参数组合数: 8")
    
    print("\n开始优化...")
    start_time = time.time()
    result = optimizer.optimize(
        strategy_id="long_liquidation_bounce",
        param_grid=param_grid,
        bars_data=bars_data,
        verbose=True
    )
    elapsed = time.time() - start_time
    
    print(f"\n优化完成!")
    print(f"最佳Sharpe: {result['best_score']:.4f}")
    print(f"耗时: {elapsed:.2f}秒")
    
    return elapsed


if __name__ == '__main__':
    mp_time = test_grid_search_multiprocess()
    seq_time = test_grid_search_sequential()
    
    print("\n" + "="*80)
    print("性能对比")
    print("="*80)
    print(f"多进程耗时: {mp_time:.2f}秒")
    print(f"串行耗时:   {seq_time:.2f}秒")
    if mp_time > 0:
        speedup = seq_time / mp_time
        print(f"加速比:     {speedup:.2f}x")
    print("="*80)
