"""
测试系统层 ParameterOptimizer

验证架构分层：
- engines/optimization/parallel_backtest.py: 子进程回测
- engines/optimization/parameter_optimizer.py: 参数优化器
"""
import sys
import os
import time

backend_path = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, backend_path)

from engines.optimization import ParameterOptimizer, OptimizationConfig


def load_bars_data(year=2022):
    """加载测试数据"""
    from infrastructure.storage.parquet_reader import read_parquet_safe
    
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


def test_multiprocess():
    """测试多进程优化"""
    print("="*80)
    print("测试系统层 ParameterOptimizer (多进程)")
    print("="*80)
    
    bars_data = load_bars_data(2022)
    print(f"加载数据: {len(bars_data)} bars")
    
    optimizer = ParameterOptimizer(
        executor="process",
        max_workers=15,
        enable_gpu=False,
        config=OptimizationConfig()
    )
    
    param_grid = {
        "drop_threshold": [-0.015, -0.02],
        "rsi_threshold": [20, 25],
        "volume_ratio_threshold": [1.5, 2.0]
    }
    
    print(f"\n参数组合数: {2 * 2 * 2} = 8")
    print(f"执行器: {optimizer.executor}")
    print(f"最大工作进程: {optimizer.max_workers}")
    
    print("\n" + "-"*80)
    print("开始优化...")
    print("-"*80)
    
    start_time = time.time()
    result = optimizer.optimize(
        strategy_id="long_liquidation_bounce",
        param_grid=param_grid,
        bars_data=bars_data
    )
    elapsed = time.time() - start_time
    
    print("\n" + "="*80)
    print("优化结果")
    print("="*80)
    print(f"最佳参数: {result.best_params}")
    print(f"最佳Sharpe: {result.best_sharpe:.4f}")
    print(f"交易次数: {result.best_trades}")
    print(f"总收益: {result.best_return:.4f}")
    print(f"耗时: {result.elapsed_time:.2f}秒")
    print(f"参数组合数: {result.num_combinations}")
    print(f"工作进程数: {result.num_workers}")
    print("="*80)
    
    return result


def test_sequential():
    """测试串行优化"""
    print("\n" + "="*80)
    print("测试系统层 ParameterOptimizer (串行)")
    print("="*80)
    
    bars_data = load_bars_data(2022)
    
    optimizer = ParameterOptimizer(
        executor="sequential",
        enable_gpu=False,
        config=OptimizationConfig()
    )
    
    param_grid = {
        "drop_threshold": [-0.015, -0.02],
        "rsi_threshold": [20, 25],
        "volume_ratio_threshold": [1.5, 2.0]
    }
    
    print(f"\n参数组合数: 8")
    print(f"执行器: {optimizer.executor}")
    
    print("\n" + "-"*80)
    print("开始优化...")
    print("-"*80)
    
    start_time = time.time()
    result = optimizer.optimize(
        strategy_id="long_liquidation_bounce",
        param_grid=param_grid,
        bars_data=bars_data
    )
    elapsed = time.time() - start_time
    
    print("\n" + "="*80)
    print("串行优化结果")
    print("="*80)
    print(f"最佳Sharpe: {result.best_sharpe:.4f}")
    print(f"耗时: {result.elapsed_time:.2f}秒")
    print("="*80)
    
    return result


if __name__ == '__main__':
    mp_result = test_multiprocess()
    seq_result = test_sequential()
    
    print("\n" + "="*80)
    print("性能对比")
    print("="*80)
    print(f"多进程耗时: {mp_result.elapsed_time:.2f}秒")
    print(f"串行耗时:   {seq_result.elapsed_time:.2f}秒")
    if mp_result.elapsed_time > 0:
        speedup = seq_result.elapsed_time / mp_result.elapsed_time
        print(f"加速比:     {speedup:.2f}x")
    print("="*80)
