"""
GPU 加速参数优化和回测脚本

使用模拟数据进行测试：
- 参数优化期：模拟 2024年数据
- 回测期：模拟 2025年1月-2026年4月数据

运行方式：
    python scripts/gpu_optimize_backtest.py
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import time

sys.path.insert(0, str(Path(__file__).parent.parent))

print("=" * 70)
print("GPU Accelerated Parameter Optimization and Backtest")
print("=" * 70)

print("\n1. Checking GPU availability...")
try:
    import torch
    print(f"   PyTorch version: {torch.__version__}")
    print(f"   CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"   CUDA version: {torch.version.cuda}")
        print(f"   Device count: {torch.cuda.device_count()}")
        print(f"   Device name: {torch.cuda.get_device_name(0)}")
        print(f"   Device memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
        DEVICE = "cuda"
    else:
        print("   CUDA not available, using CPU")
        DEVICE = "cpu"
except ImportError as e:
    print(f"   PyTorch not installed: {e}")
    print("   Using CPU only")
    DEVICE = "cpu"

print(f"\n   Selected device: {DEVICE}")

print("\n2. Generating simulated data...")
np.random.seed(42)

n_optimization = 50000
n_backtest = 30000

def generate_kline_data(n_rows, start_date, initial_price=50000):
    timestamps = pd.date_range(start=start_date, periods=n_rows, freq='1min')
    
    returns = np.random.randn(n_rows) * 0.002
    prices = initial_price * np.exp(np.cumsum(returns))
    
    df = pd.DataFrame({
        'timestamp': timestamps,
        'open': prices * (1 + np.random.randn(n_rows) * 0.0005),
        'high': prices * (1 + np.abs(np.random.randn(n_rows)) * 0.001),
        'low': prices * (1 - np.abs(np.random.randn(n_rows)) * 0.001),
        'close': prices,
        'volume': np.random.uniform(100, 1000, n_rows),
    })
    
    df['high'] = df[['open', 'high', 'close']].max(axis=1)
    df['low'] = df[['open', 'low', 'close']].min(axis=1)
    
    return df

df_optimization = generate_kline_data(n_optimization, '2024-01-01', 50000)
df_backtest = generate_kline_data(n_backtest, '2025-01-01', df_optimization['close'].iloc[-1])

print(f"   Optimization data: {len(df_optimization):,} rows")
print(f"   Optimization period: {df_optimization['timestamp'].min()} to {df_optimization['timestamp'].max()}")
print(f"   Backtest data: {len(df_backtest):,} rows")
print(f"   Backtest period: {df_backtest['timestamp'].min()} to {df_backtest['timestamp'].max()}")

print("\n3. Initializing GPU acceleration...")
try:
    from shared.acceleration import get_accelerator_info
    info = get_accelerator_info()
    print(f"   Backend: {info['backend']}")
    print(f"   Device type: {info['device_type']}")
    print(f"   Is GPU: {info['is_gpu']}")
except Exception as e:
    print(f"   Acceleration layer error: {e}")
    print("   Continuing with CPU...")

print("\n4. Computing features with GPU acceleration...")
start_time = time.time()

try:
    from domain.feature.torch_calculator import TorchFeatureCalculator
    
    calculator = TorchFeatureCalculator()
    
    print(f"   Computing optimization features...")
    features_opt = calculator.compute_batch(df_optimization, symbol="BTCUSDT", use_gpu=(DEVICE == "cuda"))
    
    print(f"   Computing backtest features...")
    features_backtest = calculator.compute_batch(df_backtest, symbol="BTCUSDT", use_gpu=(DEVICE == "cuda"))
    
    feature_time = time.time() - start_time
    print(f"   Feature computation completed in {feature_time:.1f}s")
    print(f"   Features computed: {len(features_opt.columns) - 6}")
    
except Exception as e:
    print(f"   Feature computation error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n5. Running parameter optimization...")
start_time = time.time()

try:
    from application.optimization_service.parallel_engine import (
        ParallelBacktestEngine, BacktestConfig, generate_param_grid, run_single_backtest
    )
    
    config = BacktestConfig(
        initial_capital=10000,
        commission=0.0005,
        slippage=0.0002,
        position_size=0.3,
        stop_loss=0.02,
        take_profit=0.04,
    )
    
    param_grid = generate_param_grid("rsi_oversold", {
        "period": [7, 14, 21],
        "threshold": [20, 25, 30],
    })
    
    print(f"   Parameter combinations: {len(param_grid)}")
    
    optimization_data_path = Path(__file__).parent.parent / "data_lake" / "temp_optimization.parquet"
    optimization_data_path.parent.mkdir(parents=True, exist_ok=True)
    features_opt.to_parquet(optimization_data_path, index=False)
    
    results = []
    for params in param_grid:
        result = run_single_backtest(
            str(optimization_data_path),
            "BTCUSDT",
            "rsi_oversold",
            params,
            config,
            int(df_optimization['timestamp'].min().timestamp() * 1000),
            int(df_optimization['timestamp'].max().timestamp() * 1000),
        )
        results.append(result)
    
    results = sorted(results, key=lambda r: r.sharpe_ratio, reverse=True)
    
    optimization_time = time.time() - start_time
    print(f"\n   Optimization completed in {optimization_time:.1f}s")
    print(f"   Results: {len(results)} parameter combinations tested")
    
    if results:
        best = results[0]
        print(f"\n   Best parameters:")
        print(f"     Period: {best.params.get('period')}")
        print(f"     Oversold: {best.params.get('oversold')}")
        print(f"     Sharpe Ratio: {best.sharpe_ratio:.2f}")
        print(f"     Total Return: {best.total_return*100:.1f}%")
        print(f"     Win Rate: {best.win_rate*100:.1f}%")
        print(f"     Max Drawdown: {best.max_drawdown*100:.1f}%")
        print(f"     Total Trades: {best.total_trades}")
        
        best_params = best.params
    else:
        print("   No valid results, using default parameters")
        best_params = {"period": 14, "oversold": 30}
    
except Exception as e:
    print(f"   Optimization error: {e}")
    import traceback
    traceback.print_exc()
    best_params = {"period": 14, "oversold": 30}

print("\n6. Running backtest with optimized parameters...")
start_time = time.time()

try:
    period = best_params.get("period", 14)
    oversold = best_params.get("oversold", 30)
    
    rsi_col = f"rsi_{period}"
    
    if rsi_col not in features_backtest.columns:
        print(f"   WARNING: {rsi_col} not found, using rsi_14")
        rsi_col = "rsi_14"
    
    capital = 10000
    position = None
    trades = []
    equity_curve = [capital]
    
    for idx, row in features_backtest.iterrows():
        rsi = row.get(rsi_col, 50)
        close = row.get('close', 0)
        
        if position:
            pnl_pct = (close - position['entry_price']) / position['entry_price']
            
            if pnl_pct <= -0.02:
                pnl = position['quantity'] * close * pnl_pct
                capital += position['quantity'] * close + pnl
                trades.append({
                    'entry_time': position['entry_time'],
                    'exit_time': row.get('timestamp'),
                    'entry_price': position['entry_price'],
                    'exit_price': close,
                    'pnl_pct': pnl_pct,
                    'exit_reason': 'stop_loss',
                })
                position = None
            elif pnl_pct >= 0.04:
                pnl = position['quantity'] * close * pnl_pct
                capital += position['quantity'] * close + pnl
                trades.append({
                    'entry_time': position['entry_time'],
                    'exit_time': row.get('timestamp'),
                    'entry_price': position['entry_price'],
                    'exit_price': close,
                    'pnl_pct': pnl_pct,
                    'exit_reason': 'take_profit',
                })
                position = None
        
        if position is None and rsi < oversold:
            position_size = capital * 0.3
            quantity = position_size / close
            position = {
                'entry_time': row.get('timestamp'),
                'entry_price': close,
                'quantity': quantity,
            }
            capital -= position_size
        
        current_equity = capital
        if position:
            unrealized_pnl = (close - position['entry_price']) / position['entry_price']
            current_equity += position['quantity'] * position['entry_price'] * unrealized_pnl
        equity_curve.append(current_equity)
    
    if position:
        last_close = features_backtest.iloc[-1]['close']
        pnl_pct = (last_close - position['entry_price']) / position['entry_price']
        capital += position['quantity'] * last_close
        trades.append({
            'entry_time': position['entry_time'],
            'exit_time': features_backtest.iloc[-1].get('timestamp'),
            'entry_price': position['entry_price'],
            'exit_price': last_close,
            'pnl_pct': pnl_pct,
            'exit_reason': 'end',
        })
    
    total_return = (capital - 10000) / 10000
    winning_trades = [t for t in trades if t['pnl_pct'] > 0]
    losing_trades = [t for t in trades if t['pnl_pct'] <= 0]
    win_rate = len(winning_trades) / len(trades) if trades else 0
    
    peak = 10000
    max_dd = 0
    for eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak
        if dd > max_dd:
            max_dd = dd
    
    backtest_time = time.time() - start_time
    
    print(f"\n   Backtest completed in {backtest_time:.1f}s")
    
    print("\n" + "=" * 70)
    print("BACKTEST RESULTS")
    print("=" * 70)
    print(f"\n   Period: {df_backtest['timestamp'].min().date()} to {df_backtest['timestamp'].max().date()}")
    print(f"   Strategy: RSI Oversold (period={period}, oversold={oversold})")
    print(f"   GPU Accelerated: {DEVICE == 'cuda'}")
    print(f"\n   Performance:")
    print(f"     Total Return: {total_return*100:.1f}%")
    print(f"     Final Capital: ${capital:,.2f}")
    print(f"     Max Drawdown: {max_dd*100:.1f}%")
    print(f"     Win Rate: {win_rate*100:.1f}%")
    print(f"     Total Trades: {len(trades)}")
    print(f"     Winning Trades: {len(winning_trades)}")
    print(f"     Losing Trades: {len(losing_trades)}")
    
    if trades:
        avg_win = sum(t['pnl_pct'] for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(t['pnl_pct'] for t in losing_trades) / len(losing_trades) if losing_trades else 0
        print(f"     Avg Win: {avg_win*100:.1f}%")
        print(f"     Avg Loss: {avg_loss*100:.1f}%")
    
    print("\n" + "=" * 70)
    
except Exception as e:
    print(f"   Backtest error: {e}")
    import traceback
    traceback.print_exc()

print("\nDone!")
