"""
GPU 加速参数优化和回测脚本

使用真实数据：
- 参数优化期：2024年12月及之前的数据
- 回测期：2025年1月到2026年4月的数据

运行方式：
    python scripts/gpu_optimize_backtest.py
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
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
    DEVICE = "cpu"

print(f"\n   Selected device: {DEVICE}")

print("\n2. Loading real data...")
try:
    from shared.utils.parquet_reader import read_parquet_safe
    
    data_path = Path(__file__).parent.parent / "data_lake" / "features" / "binance" / "BTCUSDT" / "features.parquet"
    print(f"   Data path: {data_path}")
    
    if data_path.exists():
        df = read_parquet_safe(data_path)
        print(f"   Total rows: {len(df):,}")
        print(f"   Columns: {len(df.columns)}")
        
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        elif 'open_time' in df.columns:
            df['timestamp'] = pd.to_datetime(df['open_time'], unit='ms')
        
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        print(f"   Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    else:
        raise FileNotFoundError(f"Data file not found: {data_path}")
    
except Exception as e:
    print(f"   Error loading data: {e}")
    print("   Falling back to simulated data...")
    
    np.random.seed(42)
    
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
    
    df = generate_kline_data(80000, '2024-01-01', 50000)
    print(f"   Simulated data: {len(df):,} rows")

print("\n3. Splitting data...")
optimization_end = pd.Timestamp('2024-12-31 23:59:59')
backtest_start = pd.Timestamp('2025-01-01 00:00:00')
backtest_end = pd.Timestamp('2026-04-30 23:59:59')

df_optimization = df[df['timestamp'] <= optimization_end].copy()
df_backtest = df[(df['timestamp'] >= backtest_start) & (df['timestamp'] <= backtest_end)].copy()

print(f"   Optimization period: {df['timestamp'].min()} to {optimization_end}")
print(f"   Optimization rows: {len(df_optimization):,}")
print(f"   Backtest period: {backtest_start} to {backtest_end}")
print(f"   Backtest rows: {len(df_backtest):,}")

if len(df_optimization) < 1000:
    print("   WARNING: Not enough optimization data, using 80% of data")
    split_idx = int(len(df) * 0.8)
    df_optimization = df.iloc[:split_idx].copy()
    df_backtest = df.iloc[split_idx:].copy()
    print(f"   Adjusted optimization rows: {len(df_optimization):,}")
    print(f"   Adjusted backtest rows: {len(df_backtest):,}")

print("\n4. Initializing GPU acceleration...")
try:
    from shared.acceleration import get_accelerator_info
    info = get_accelerator_info()
    print(f"   Backend: {info['backend']}")
    print(f"   Device type: {info['device_type']}")
    print(f"   Is GPU: {info['is_gpu']}")
except Exception as e:
    print(f"   Acceleration layer error: {e}")

print("\n5. Computing features with GPU acceleration...")
start_time = time.time()

try:
    from domain.feature.torch_calculator import TorchFeatureCalculator
    
    calculator = TorchFeatureCalculator()
    
    print(f"   Computing optimization features ({len(df_optimization):,} rows)...")
    features_opt = calculator.compute_batch(df_optimization, symbol="BTCUSDT", use_gpu=(DEVICE == "cuda"))
    
    feature_time_opt = time.time() - start_time
    print(f"   Optimization features computed in {feature_time_opt:.1f}s")
    
    start_time = time.time()
    print(f"   Computing backtest features ({len(df_backtest):,} rows)...")
    features_backtest = calculator.compute_batch(df_backtest, symbol="BTCUSDT", use_gpu=(DEVICE == "cuda"))
    
    feature_time_backtest = time.time() - start_time
    print(f"   Backtest features computed in {feature_time_backtest:.1f}s")
    
    feature_cols = [c for c in features_opt.columns if c not in ['timestamp', 'open', 'high', 'low', 'close', 'volume']]
    print(f"   Features computed: {len(feature_cols)}")
    print(f"   Sample features: {feature_cols[:5]}...")
    
except Exception as e:
    print(f"   Feature computation error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n6. Running parameter optimization...")
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
        "threshold": [20, 25, 30, 35],
    })
    
    print(f"   Parameter combinations: {len(param_grid)}")
    
    optimization_data_path = Path(__file__).parent.parent / "data_lake" / "temp_optimization.parquet"
    optimization_data_path.parent.mkdir(parents=True, exist_ok=True)
    features_opt.to_parquet(optimization_data_path, index=False)
    
    results = []
    for i, params in enumerate(param_grid):
        print(f"   Testing parameter set {i+1}/{len(param_grid)}: {params}")
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
        print(f"     Sharpe: {result.sharpe_ratio:.2f}, Return: {result.total_return*100:.1f}%, Trades: {result.total_trades}")
    
    results = sorted(results, key=lambda r: r.sharpe_ratio, reverse=True)
    
    optimization_time = time.time() - start_time
    print(f"\n   Optimization completed in {optimization_time:.1f}s")
    
    print("\n   Top 3 parameter sets:")
    for i, r in enumerate(results[:3]):
        print(f"     {i+1}. period={r.params.get('period')}, oversold={r.params.get('oversold')}")
        print(f"        Sharpe: {r.sharpe_ratio:.2f}, Return: {r.total_return*100:.1f}%, Win Rate: {r.win_rate*100:.1f}%")
    
    if results:
        best = results[0]
        best_params = best.params
    else:
        best_params = {"period": 14, "oversold": 30}
    
except Exception as e:
    print(f"   Optimization error: {e}")
    import traceback
    traceback.print_exc()
    best_params = {"period": 14, "oversold": 30}

print("\n7. Running backtest with optimized parameters...")
start_time = time.time()

try:
    period = best_params.get("period", 14)
    oversold = best_params.get("oversold", 30)
    
    rsi_col = f"rsi_{period}"
    
    if rsi_col not in features_backtest.columns:
        print(f"   WARNING: {rsi_col} not found, using rsi_14")
        rsi_col = "rsi_14"
        if rsi_col not in features_backtest.columns:
            print("   ERROR: No RSI column found!")
            sys.exit(1)
    
    capital = 10000.0
    position = None
    trades = []
    equity_curve = [capital]
    
    for idx, row in features_backtest.iterrows():
        rsi = row.get(rsi_col, 50)
        close = row.get('close', 0)
        
        if pd.isna(rsi) or pd.isna(close):
            continue
        
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
    
    if len(equity_curve) > 1:
        returns = [(equity_curve[i] - equity_curve[i-1]) / equity_curve[i-1] for i in range(1, len(equity_curve))]
        avg_return = np.mean(returns)
        std_return = np.std(returns)
        sharpe = (avg_return / std_return * np.sqrt(252 * 24 * 60)) if std_return > 0 else 0
    else:
        sharpe = 0
    
    backtest_time = time.time() - start_time
    
    print(f"\n   Backtest completed in {backtest_time:.1f}s")
    
    print("\n" + "=" * 70)
    print("BACKTEST RESULTS")
    print("=" * 70)
    print(f"\n   Optimization Period: {df_optimization['timestamp'].min().date()} to {df_optimization['timestamp'].max().date()}")
    print(f"   Backtest Period: {df_backtest['timestamp'].min().date()} to {df_backtest['timestamp'].max().date()}")
    print(f"   Strategy: RSI Oversold (period={period}, oversold={oversold})")
    print(f"   GPU Accelerated: {DEVICE == 'cuda'}")
    print(f"\n   Performance Metrics:")
    print(f"     Total Return: {total_return*100:.2f}%")
    print(f"     Annualized Return: {total_return * 100 * 365 / max((df_backtest['timestamp'].max() - df_backtest['timestamp'].min()).days, 1):.2f}%")
    print(f"     Sharpe Ratio: {sharpe:.2f}")
    print(f"     Final Capital: ${capital:,.2f}")
    print(f"     Max Drawdown: {max_dd*100:.2f}%")
    print(f"     Win Rate: {win_rate*100:.1f}%")
    print(f"     Total Trades: {len(trades)}")
    print(f"     Winning Trades: {len(winning_trades)}")
    print(f"     Losing Trades: {len(losing_trades)}")
    
    if trades:
        avg_win = sum(t['pnl_pct'] for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(t['pnl_pct'] for t in losing_trades) / len(losing_trades) if losing_trades else 0
        profit_factor = abs(sum(t['pnl_pct'] for t in winning_trades) / sum(t['pnl_pct'] for t in losing_trades)) if losing_trades and sum(t['pnl_pct'] for t in losing_trades) != 0 else 0
        print(f"     Avg Win: {avg_win*100:.2f}%")
        print(f"     Avg Loss: {avg_loss*100:.2f}%")
        print(f"     Profit Factor: {profit_factor:.2f}")
    
    print("\n" + "=" * 70)
    
    if optimization_data_path.exists():
        optimization_data_path.unlink()
    
except Exception as e:
    print(f"   Backtest error: {e}")
    import traceback
    traceback.print_exc()

print("\nDone!")
