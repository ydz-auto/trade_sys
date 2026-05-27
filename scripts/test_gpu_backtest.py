#!/usr/bin/env python3
"""Test GPU-accelerated backtest with real data"""
import sys
import os
from pathlib import Path

# Add backend path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
sys.path.insert(0, backend_path)

import pandas as pd
from infrastructure.logging import get_logger
from infrastructure.storage.parquet_reader import read_parquet_safe
from runtime.replay_runtime.backtest_engine import (
    BacktestEngine, BacktestConfig, Bar, SignalType
)

logger = get_logger("test_gpu_backtest")

def load_data():
    """Load BTCUSDT data from data_lake"""
    data_path = Path(backend_path) / "data_lake" / "crypto" / "binance" / "klines" / "symbol=BTCUSDT" / "year=2022" / "month=01" / "data.parquet"
    
    if not data_path.exists():
        logger.error(f"Data not found: {data_path}")
        return []
    
    logger.info(f"Loading data from {data_path}")
    df = read_parquet_safe(data_path)
    if df is None or len(df) == 0:
        logger.warning("No data loaded")
        return []
    
    bars = []
    for _, row in df.iterrows():
        try:
            if 'timestamp' in df.columns:
                ts = pd.to_datetime(row['timestamp'])
            elif 'open_time' in df.columns:
                ts = pd.to_datetime(row['open_time'], unit='ms')
            else:
                continue
            bar = Bar(
                timestamp=ts,
                open=float(row.get('open', 0)),
                high=float(row.get('high', 0)),
                low=float(row.get('low', 0)),
                close=float(row.get('close', 0)),
                volume=float(row.get('volume', 0)),
            )
            bars.append(bar)
        except Exception as e:
            logger.debug(f"Error parsing bar: {e}")
            continue
    
    logger.info(f"Loaded {len(bars)} bars")
    return bars

def simple_strategy(bar, position=None):
    """Simple random strategy"""
    import random
    if random.random() < 0.01:
        return SignalType.BUY
    elif random.random() < 0.01:
        return SignalType.SELL
    return SignalType.HOLD

def main():
    print("Testing GPU-accelerated backtest engine")
    print("="*80)
    
    # Load data
    bars = load_data()
    if len(bars) == 0:
        print("No data to test!")
        return
    
    # Test with GPU
    print("\nTesting with GPU acceleration...")
    config_gpu = BacktestConfig(
        initial_capital=10000.0,
        commission=0.0004,
        slippage=0.0005,
        position_size=0.1,
        stop_loss=0.1,
        take_profit=0.2,
        leverage=1.0,
        use_realistic_fees=True,
    )
    
    engine_gpu = BacktestEngine(config=config_gpu, enable_gpu=True)
    engine_gpu.load_data(bars)
    result_gpu = engine_gpu.run(simple_strategy)
    
    print("\nGPU Test Results:")
    final_equity = result_gpu.equity_curve[-1] if result_gpu.equity_curve else 0.0
    print(f"  Final equity: ${final_equity:.2f}")
    print(f"  Total return: ${result_gpu.metrics.total_return:.2f}")
    print(f"  Total return (%): {result_gpu.metrics.total_return_pct:.2%}")
    print(f"  Total trades: {result_gpu.metrics.total_trades}")
    print(f"  Sharpe ratio: {result_gpu.metrics.sharpe_ratio:.4f}")
    print(f"  Max drawdown: {result_gpu.metrics.max_drawdown_pct:.2%}")
    
    # Test without GPU for comparison
    print("\nTesting without GPU acceleration...")
    config_cpu = BacktestConfig(
        initial_capital=10000.0,
        commission=0.0004,
        slippage=0.0005,
        position_size=0.1,
        stop_loss=0.1,
        take_profit=0.2,
        leverage=1.0,
        use_realistic_fees=True,
    )
    
    engine_cpu = BacktestEngine(config=config_cpu, enable_gpu=False)
    engine_cpu.load_data(bars)
    result_cpu = engine_cpu.run(simple_strategy)
    
    print("\nCPU Test Results:")
    final_equity_cpu = result_cpu.equity_curve[-1] if result_cpu.equity_curve else 0.0
    print(f"  Final equity: ${final_equity_cpu:.2f}")
    print(f"  Total return: ${result_cpu.metrics.total_return:.2f}")
    print(f"  Total return (%): {result_cpu.metrics.total_return_pct:.2%}")
    print(f"  Total trades: {result_cpu.metrics.total_trades}")
    print(f"  Sharpe ratio: {result_cpu.metrics.sharpe_ratio:.4f}")
    print(f"  Max drawdown: {result_cpu.metrics.max_drawdown_pct:.2%}")
    
    print("\n✅ Backtest test completed!")

if __name__ == "__main__":
    main()
