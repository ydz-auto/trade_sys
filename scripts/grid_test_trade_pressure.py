#!/usr/bin/env python3
"""
参数敏感性测试 - Grid Search (使用 CPU 多进程加速)
"""
import sys
import os
from pathlib import Path
from itertools import product
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

script_dir = os.path.dirname(os.path.abspath(__file__))
backend_path = os.path.abspath(os.path.join(script_dir, '..', 'backend'))
sys.path.insert(0, backend_path)

from infrastructure.storage.parquet_reader import read_parquet_safe
from engines.compute.strategy.registry import get_strategy, get_strategy_info
import numpy as np


def load_data(year=2023, max_bars=30000):
    data_path = Path(backend_path) / "data_lake" / "crypto" / "binance" / "klines" / "symbol=BTCUSDT" / f"year={year}"
    bars = []
    
    if data_path.exists():
        for month_dir in sorted(data_path.iterdir())[:3]:
            if month_dir.is_dir() and month_dir.name.startswith("month="):
                parquet_file = month_dir / "data.parquet"
                if parquet_file.exists():
                    df = read_parquet_safe(parquet_file)
                    if df is not None:
                        for _, row in df.iterrows():
                            try:
                                bar = {
                                    "timestamp": row["timestamp"],
                                    "open": float(row["open"]),
                                    "high": float(row["high"]),
                                    "low": float(row["low"]),
                                    "close": float(row["close"]),
                                    "volume": float(row["volume"])
                                }
                                bars.append(bar)
                                if len(bars) >= max_bars:
                                    break
                            except:
                                pass
                if len(bars) >= max_bars:
                    break
    
    print(f"Loaded {len(bars)} bars")
    return bars


def run_single_test(args):
    """在子进程中运行单个参数组合测试"""
    strategy_id, params, zscore_window, bars = args
    
    try:
        strategy = get_strategy(strategy_id, params)
    except Exception as e:
        return None
    
    prev_closes = []
    prev_volumes = []
    prev_cvds = []
    
    equity = 10000.0
    initial_capital = equity
    position_size = 0.1
    leverage = 1.0
    slippage = 0.0005
    in_position = False
    position_type = None
    entry_price = 0
    trades = []
    signal_count = 0
    
    def calculate_cvd():
        if len(prev_closes) < 2:
            return 0.0
        price_diff = np.diff(prev_closes)
        vol_array = np.array(prev_volumes[1:])
        return float(np.sum(np.where(price_diff > 0, vol_array, -vol_array)))
    
    def calculate_zscore(values, period):
        period = min(period, len(values))
        if period < 10:
            return 0.0
        recent = np.array(values[-period:])
        mean = np.mean(recent)
        std = np.std(recent)
        return (values[-1] - mean) / std if std > 0 else 0.0
    
    def calculate_volume_zscore(period):
        period = min(period, len(prev_volumes))
        if period < 10:
            return 0.0
        recent = np.array(prev_volumes[-period:])
        mean = np.mean(recent)
        std = np.std(recent)
        return (prev_volumes[-1] - mean) / std if std > 0 else 0.0
    
    for bar in bars:
        prev_closes.append(bar["close"])
        prev_volumes.append(bar["volume"])
        
        if len(prev_closes) > 600:
            prev_closes = prev_closes[-600:]
            prev_volumes = prev_volumes[-600:]
        
        cvd = calculate_cvd()
        prev_cvds.append(cvd)
        if len(prev_cvds) > 1000:
            prev_cvds = prev_cvds[-1000:]
        
        cvd_zscore = calculate_zscore(prev_cvds, zscore_window)
        volume_zscore = calculate_volume_zscore(zscore_window)
        
        features = {
            "close": bar["close"],
            "high": bar["high"],
            "low": bar["low"],
            "volume": bar["volume"],
            "close_prices": prev_closes,
            "volumes": prev_volumes,
            "symbol": "BTCUSDT",
            "timestamp": bar["timestamp"]
        }
        
        if len(prev_volumes) > 24:
            current_vol = prev_volumes[-1]
            avg_vol = np.mean(prev_volumes[-25:-1]) if len(prev_volumes) > 25 else np.mean(prev_volumes)
            features["volume_ratio"] = current_vol / avg_vol if avg_vol > 0 else 1.0
        
        features["cvd"] = cvd if len(prev_cvds) > 0 else 0
        features["cvd_zscore"] = cvd_zscore
        features["volume_zscore"] = volume_zscore
        
        if len(prev_closes) > 24:
            features["return_1h"] = (prev_closes[-1] - prev_closes[-24]) / prev_closes[-24]
        
        if len(prev_closes) > 10:
            price_moves = np.diff(prev_closes[-10:])
            up_vol = np.sum(np.where(price_moves > 0, prev_volumes[-9:], 0))
            down_vol = np.sum(np.where(price_moves < 0, prev_volumes[-9:], 0))
            total = up_vol + down_vol
            features["taker_buy_ratio"] = up_vol / total if total > 0 else 0.5
        
        try:
            signal_dict = strategy.generate_signal(features)
            if signal_dict and not in_position:
                entry_price = prev_closes[-1] * (1 + slippage)
                in_position = True
                position_type = "long"
                signal_count += 1
                trades.append({"entry_price": entry_price, "entry_equity": equity, "pnl": 0})
            elif signal_dict and in_position:
                exit_price = prev_closes[-1] * (1 - slippage)
                price_return = (exit_price - entry_price) / entry_price if position_type == "long" else (entry_price - exit_price) / entry_price
                margin = equity * position_size
                pnl = margin * price_return * leverage
                equity = equity + pnl
                trades[-1]["pnl"] = pnl
                in_position = False
        except:
            pass
    
    if in_position and prev_closes:
        exit_price = prev_closes[-1] * (1 - slippage)
        price_return = (exit_price - entry_price) / entry_price if position_type == "long" else (entry_price - exit_price) / entry_price
        margin = equity * position_size
        pnl = margin * price_return * leverage
        equity = equity + pnl
        trades[-1]["pnl"] = pnl
    
    total_trades = len(trades)
    total_return = (equity - initial_capital) / initial_capital * 100
    
    if total_trades == 0:
        return {
            "strategy": strategy_id,
            "params": params,
            "zscore_window": zscore_window,
            "signals": signal_count,
            "trades": 0,
            "return": 0,
            "sharpe": 0,
            "win_rate": 0,
            "pf": 0,
        }
    
    winning = [t for t in trades if t["pnl"] > 0]
    win_rate = len(winning) / total_trades
    gross_profit = sum(t["pnl"] for t in winning)
    gross_loss = abs(sum(t["pnl"] for t in trades if t["pnl"] <= 0))
    pf = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    returns = [t["pnl"] for t in trades]
    sharpe = np.mean(returns) / np.std(returns) * np.sqrt(len(returns)) if len(returns) > 1 and np.std(returns) > 0 else 0
    
    return {
        "strategy": strategy_id,
        "params": params,
        "zscore_window": zscore_window,
        "signals": signal_count,
        "trades": total_trades,
        "return": total_return,
        "sharpe": sharpe,
        "win_rate": win_rate,
        "pf": pf,
    }


def test_strategy_grid_parallel(strategy_id, param_grid, bars, min_trades=30, max_workers=None):
    print(f"\n{'='*80}")
    print(f"GRID TEST (PARALLEL): {strategy_id}")
    print(f"{'='*80}")
    
    keys = list(param_grid.keys())
    values = list(param_grid.values())
    combinations = list(product(*values))
    
    tasks = []
    for combo in combinations:
        params = dict(zip(keys, combo))
        zscore_window = params.pop("zscore_window", 60)
        tasks.append((strategy_id, params, zscore_window, bars))
    
    print(f"Testing {len(tasks)} parameter combinations with parallel execution...")
    
    if max_workers is None:
        max_workers = min(multiprocessing.cpu_count(), 8)
    print(f"Using {max_workers} CPU cores")
    
    results = []
    
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(run_single_test, task): task for task in tasks}
        
        completed = 0
        for future in as_completed(futures):
            completed += 1
            if completed % 20 == 0:
                print(f"  Progress: {completed}/{len(tasks)}")
            
            result = future.result()
            if result:
                results.append(result)
    
    results.sort(key=lambda x: x["trades"], reverse=True)
    
    print(f"\n{'zscore':>7} {'cvd':>5} {'vol':>5} {'signals':>8} {'trades':>6} {'return':>8} {'sharpe':>8} {'WR':>6} {'PF':>6}")
    print("-" * 75)
    
    filtered_results = []
    for r in results:
        zscore = r["zscore_window"]
        cvd = r["params"].get("cvd_threshold", r["params"].get("cvd_divergence_threshold", "-"))
        vol = r["params"].get("volume_threshold", r["params"].get("min_pressure_score", "-"))
        
        trades = r["trades"]
        
        if trades < min_trades:
            status = "❌"
        elif trades < 100:
            status = "⚠️"
        else:
            status = "✅"
            filtered_results.append(r)
        
        cvd_str = f"{cvd:.2f}" if isinstance(cvd, float) else str(cvd)
        vol_str = f"{vol:.2f}" if isinstance(vol, float) else str(vol)
        
        print(f"{zscore:>7} {cvd_str:>5} {vol_str:>5} "
              f"{r['signals']:>8} {trades:>6} {r['return']:>8.2f} {r['sharpe']:>8.2f} "
              f"{r['win_rate']*100:>6.1f} {r['pf']:>6.2f} {status}")
    
    if filtered_results:
        best = max(filtered_results, key=lambda x: x["sharpe"])
        print(f"\n🏆 BEST (trades >= {min_trades}): zscore={best['zscore_window']}, {best['params']}")
        print(f"   Sharpe={best['sharpe']:.2f}, Return={best['return']:.2f}%, Trades={best['trades']}")
    
    return results


def main():
    print("\n" + "="*80)
    print("PARAMETER SENSITIVITY TEST (CPU PARALLEL)")
    print("="*80)
    
    print("\nLoading data...")
    bars = load_data(2023, 30000)
    
    param_grid_bounce = {
        "zscore_window": [60, 120],
        "cvd_threshold": [0.8, 1.2, 1.6],
        "volume_threshold": [1.0, 1.5, 2.0],
        "min_pressure_score": [1.5, 2.0, 2.5]
    }
    
    test_strategy_grid_parallel("trade_pressure_bounce", param_grid_bounce, bars)
    
    print("\n" + "="*80)
    print("2. TEST trade_pressure_squeeze")
    print("="*80)
    
    param_grid_squeeze = {
        "zscore_window": [60, 120],
        "cvd_threshold": [0.8, 1.2, 1.6],
        "volume_threshold": [1.0, 1.5, 2.0],
        "min_pressure_score": [1.5, 2.0, 2.5]
    }
    
    test_strategy_grid_parallel("trade_pressure_squeeze", param_grid_squeeze, bars)
    
    print("\n" + "="*80)
    print("3. TEST trade_pressure_exhaustion")
    print("="*80)
    
    param_grid_exhaustion = {
        "zscore_window": [60, 120],
        "return_threshold": [0.001, 0.002, 0.005],
        "volume_threshold": [1.5, 2.0, 2.5],
        "cvd_divergence_threshold": [0.5, 1.0, 1.5]
    }
    
    test_strategy_grid_parallel("trade_pressure_exhaustion", param_grid_exhaustion, bars)
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
