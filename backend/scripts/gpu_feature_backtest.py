"""
使用系统内能力提取特征并运行 GPU 加速回测

步骤：
1. 从 data_lake/crypto/binance/klines 读取原始 K 线数据
2. 使用 TorchFeatureCalculator 提取特征（GPU 加速）
3. 参数优化
4. 回测
"""

import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np
import time

sys.path.insert(0, str(Path(__file__).parent.parent))

from application.optimization_service.parallel_engine import (
    BacktestConfig, generate_param_grid, BacktestResult
)


def _run_single_backtest_in_memory(
    df: pd.DataFrame,
    symbol: str,
    strategy_id: str,
    params: dict,
    config: BacktestConfig,
) -> BacktestResult:
    """在内存中运行单次回测"""
    period = params.get("period", 14)
    oversold = params.get("oversold", 30)
    rsi_col = f"rsi_{period}"
    
    capital = config.initial_capital
    position = None
    trades = []
    equity_curve = [config.initial_capital]
    
    for idx, row in df.iterrows():
        rsi = row.get(rsi_col, 50)
        close = row.get('close', 0)
        current_time = row.get('timestamp')
        
        if pd.isna(rsi) or pd.isna(close):
            continue
        
        if position:
            pnl_pct = (close - position['entry_price']) / position['entry_price']
            
            exit_reason = None
            if pnl_pct <= -config.stop_loss:
                exit_reason = "stop_loss"
            elif pnl_pct >= config.take_profit:
                exit_reason = "take_profit"
            
            if exit_reason:
                pnl = position['quantity'] * position['entry_price'] * pnl_pct
                capital += position['quantity'] * position['entry_price'] + pnl
                trades.append({
                    'pnl_pct': pnl_pct,
                    'exit': exit_reason,
                    'entry_time': position['entry_time'],
                    'exit_time': current_time,
                })
                position = None
        
        if position is None and rsi < oversold:
            position_size = capital * config.position_size
            position = {
                'entry_time': current_time,
                'entry_price': close,
                'quantity': position_size / close,
            }
            capital -= position_size
        
        eq = capital
        if position:
            eq += position['quantity'] * close
        equity_curve.append(eq)
    
    if position:
        last_close = df.iloc[-1]['close']
        pnl_pct = (last_close - position['entry_price']) / position['entry_price']
        capital += position['quantity'] * position['entry_price'] * (1 + pnl_pct)
        trades.append({
            'pnl_pct': pnl_pct,
            'exit': 'end',
            'entry_time': position['entry_time'],
            'exit_time': df.iloc[-1]['timestamp'],
        })
    
    total_return = (capital - config.initial_capital) / config.initial_capital
    wins = [t for t in trades if t['pnl_pct'] > 0]
    win_rate = len(wins) / len(trades) if trades else 0
    
    returns = [t['pnl_pct'] for t in trades]
    sharpe = np.mean(returns) / (np.std(returns) + 1e-10) * np.sqrt(252) if returns else 0
    
    peak = config.initial_capital
    max_dd = 0
    for eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak
        if dd > max_dd:
            max_dd = dd
    
    return BacktestResult(
        symbol=symbol,
        strategy_id=strategy_id,
        params=params,
        total_return=total_return,
        annualized_return=total_return * 252 / 365,
        win_rate=win_rate,
        sharpe_ratio=sharpe,
        max_drawdown=max_dd,
        total_trades=len(trades),
        winning_trades=len(wins),
        losing_trades=len(trades) - len(wins),
    )


print("=" * 70)
print("GPU Accelerated Feature Extraction and Backtest")
print("=" * 70)

print("\n1. Checking GPU...")
try:
    import torch
    print(f"   PyTorch: {torch.__version__}")
    print(f"   CUDA: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"   Device: {torch.cuda.get_device_name(0)}")
        print(f"   Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
        DEVICE = "cuda"
    else:
        DEVICE = "cpu"
except:
    DEVICE = "cpu"

print("\n2. Loading raw kline data from data_lake...")
from shared.utils.parquet_reader import read_parquet_safe

data_lake_root = Path(r"e:\00_crypto\00_code\backend\data_lake")
kline_path = data_lake_root / "crypto" / "binance" / "klines" / "symbol=BTCUSDT"

print(f"   Kline path: {kline_path}")

dfs = []
for year_dir in sorted(kline_path.glob("year=*")):
    year = year_dir.name.split("=")[1]
    for month_dir in sorted(year_dir.glob("month=*")):
        parquet_file = month_dir / "data.parquet"
        if parquet_file.exists():
            try:
                df = read_parquet_safe(parquet_file)
                if not df.empty:
                    dfs.append(df)
                    print(f"   Loaded: {year}/{month_dir.name.split('=')[1]} ({len(df)} rows)")
            except Exception as e:
                print(f"   Error loading {parquet_file}: {e}")

if not dfs:
    print("   ERROR: No kline data found!")
    sys.exit(1)

df = pd.concat(dfs, ignore_index=True)
print(f"\n   Total rows: {len(df):,}")
print(f"   Columns: {list(df.columns)}")

if 'open_time' in df.columns:
    df['timestamp'] = pd.to_datetime(df['open_time'], unit='ms')
elif 'timestamp' in df.columns:
    df['timestamp'] = pd.to_datetime(df['timestamp'])

df = df.sort_values('timestamp').reset_index(drop=True)
print(f"   Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")

print("\n3. Splitting data...")
optimization_end = pd.Timestamp('2024-12-31 23:59:59')
backtest_start = pd.Timestamp('2025-01-01 00:00:00')
backtest_end = pd.Timestamp('2026-04-30 23:59:59')

df_opt = df[df['timestamp'] <= optimization_end].copy()
df_backtest = df[(df['timestamp'] >= backtest_start) & (df['timestamp'] <= backtest_end)].copy()

print(f"   Optimization: {len(df_opt):,} rows ({df_opt['timestamp'].min().date() if len(df_opt) > 0 else 'N/A'} to {df_opt['timestamp'].max().date() if len(df_opt) > 0 else 'N/A'})")
print(f"   Backtest: {len(df_backtest):,} rows ({df_backtest['timestamp'].min().date() if len(df_backtest) > 0 else 'N/A'} to {df_backtest['timestamp'].max().date() if len(df_backtest) > 0 else 'N/A'})")

if len(df_opt) < 1000:
    print("   WARNING: Not enough optimization data, using 80% split")
    split_idx = int(len(df) * 0.8)
    df_opt = df.iloc[:split_idx].copy()
    df_backtest = df.iloc[split_idx:].copy()

print("\n4. Extracting features with GPU acceleration...")
start_time = time.time()

from domain.feature.torch_calculator import TorchFeatureCalculator

calculator = TorchFeatureCalculator()

print(f"   Extracting optimization features ({len(df_opt):,} rows)...")
features_opt = calculator.compute_batch(df_opt, symbol="BTCUSDT", use_gpu=(DEVICE == "cuda"))
opt_time = time.time() - start_time
print(f"   Done in {opt_time:.1f}s")

start_time = time.time()
print(f"   Extracting backtest features ({len(df_backtest):,} rows)...")
features_backtest = calculator.compute_batch(df_backtest, symbol="BTCUSDT", use_gpu=(DEVICE == "cuda"))
backtest_time = time.time() - start_time
print(f"   Done in {backtest_time:.1f}s")

feature_cols = [c for c in features_opt.columns if c not in ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'open_time']]
print(f"\n   Features extracted: {len(feature_cols)}")
print(f"   Sample: {feature_cols[:5]}...")

print("\n5. Parameter optimization...")
start_time = time.time()

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

results = []
for i, params in enumerate(param_grid):
    result = _run_single_backtest_in_memory(
        features_opt,
        "BTCUSDT",
        "rsi_oversold",
        params,
        config,
    )
    results.append(result)
    print(f"   {i+1}/{len(param_grid)} period={params['period']}, oversold={params['oversold']}: Sharpe={result.sharpe_ratio:.2f}, Return={result.total_return*100:.1f}%")

results = sorted(results, key=lambda r: r.sharpe_ratio, reverse=True)
opt_time = time.time() - start_time
print(f"\n   Optimization completed in {opt_time:.1f}s")

print("\n   Top 3 parameters:")
for i, r in enumerate(results[:3]):
    print(f"     {i+1}. period={r.params['period']}, oversold={r.params['oversold']}")
    print(f"        Sharpe={r.sharpe_ratio:.2f}, Return={r.total_return*100:.1f}%, WinRate={r.win_rate*100:.1f}%")

best_params = results[0].params if results else {"period": 14, "oversold": 30}

print("\n6. Backtesting with optimized parameters...")
start_time = time.time()

period = best_params.get("period", 14)
oversold = best_params.get("oversold", 30)
rsi_col = f"rsi_{period}"

if rsi_col not in features_backtest.columns:
    rsi_col = "rsi_14"

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
            capital += position['quantity'] * close * (1 + pnl_pct)
            trades.append({'pnl_pct': pnl_pct, 'exit': 'stop_loss'})
            position = None
        elif pnl_pct >= 0.04:
            capital += position['quantity'] * close * (1 + pnl_pct)
            trades.append({'pnl_pct': pnl_pct, 'exit': 'take_profit'})
            position = None
    
    if position is None and rsi < oversold:
        position_size = capital * 0.3
        position = {
            'entry_price': close,
            'quantity': position_size / close,
        }
        capital -= position_size
    
    eq = capital
    if position:
        eq += position['quantity'] * close
    equity_curve.append(eq)

if position:
    capital += position['quantity'] * features_backtest.iloc[-1]['close']

total_return = (capital - 10000) / 10000
winning = [t for t in trades if t['pnl_pct'] > 0]
win_rate = len(winning) / len(trades) if trades else 0

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
print("RESULTS")
print("=" * 70)
print(f"\n   GPU Accelerated: {DEVICE == 'cuda'}")
print(f"   Optimization Period: {df_opt['timestamp'].min().date()} to {df_opt['timestamp'].max().date()}")
print(f"   Backtest Period: {df_backtest['timestamp'].min().date()} to {df_backtest['timestamp'].max().date()}")
print(f"   Strategy: RSI Oversold (period={period}, oversold={oversold})")
print(f"\n   Performance:")
print(f"     Total Return: {total_return*100:.2f}%")
print(f"     Final Capital: ${capital:,.2f}")
print(f"     Max Drawdown: {max_dd*100:.2f}%")
print(f"     Win Rate: {win_rate*100:.1f}%")
print(f"     Total Trades: {len(trades)}")
print("=" * 70)

print("\nDone!")
