#!/usr/bin/env python3
"""
批量验证所有不需要OI数据的策略（使用CPU多进程加速）
"""
import sys
import os
from pathlib import Path
from itertools import product
import multiprocessing

script_dir = os.path.dirname(os.path.abspath(__file__))
backend_path = os.path.abspath(os.path.join(script_dir, '..', 'backend'))
sys.path.insert(0, backend_path)

from infrastructure.acceleration import CPUExecutor, get_default_workers
from infrastructure.storage.parquet_reader import read_parquet_safe
from engines.compute.strategy.registry import get_strategy, get_strategy_info, list_strategies
import numpy as np

# 不需要OI数据的策略列表
STRATEGIES_TO_TEST = [
    "rsi",
    "macd",
    "sma",
    "ema",
    "bb",
    "panic_reversal",
    "long_liquidation_bounce",
    "volume_climax_fade",
    "weak_bounce_short",
    "dead_cat_echo",
    "imbalance_pressure",
    "sweep_detection",
    "liquidity_vacuum",
    "aggressive_flow",
    "breakout",
    "trend_following",
    "volatility_expansion",
    "bb_compression_breakout",
    "momentum_ignition",
    "momentum",
    "premium_divergence",
    "funding_extreme_reversal",
    "cvd_divergence",
    "whale_trade",
    "funding_settlement",
    "trade_pressure_bounce",
    "trade_pressure_squeeze",
    "trade_pressure_absorption",
    "trade_pressure_exhaustion",
    "cvd_divergence_enhanced",
]

# 使用之前grid test找到的最佳参数
BEST_PARAMS = {
    "trade_pressure_bounce": {
        "cvd_threshold": 1.6,
        "volume_threshold": 1.0,
        "min_pressure_score": 2.5,
        "zscore_window": 60,
    },
    "trade_pressure_squeeze": {
        "cvd_threshold": 1.6,
        "volume_threshold": 2.0,
        "min_pressure_score": 2.5,
        "zscore_window": 120,
    },
    "trade_pressure_exhaustion": {
        "return_threshold": 0.001,
        "volume_threshold": 2.0,
        "cvd_divergence_threshold": 0.5,
        "zscore_window": 60,
    },
}

def load_data(year=2023, max_bars=100000):
    data_path = Path(backend_path) / "data_lake" / "crypto" / "binance" / "klines" / "symbol=BTCUSDT" / f"year={year}"
    bars = []
    
    if data_path.exists():
        for month_dir in sorted(data_path.iterdir()):
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
    
    print(f"Loaded {len(bars)} bars for {year}")
    return bars

def run_single_backtest(args):
    """单个策略的回测"""
    strategy_id, params, bars = args
    
    try:
        strategy = get_strategy(strategy_id, params)
    except Exception as e:
        return {
            "strategy": strategy_id,
            "error": str(e),
            "trades": 0,
            "return": 0,
            "sharpe": 0,
        }
    
    prev_closes = []
    prev_volumes = []
    prev_cvds = []
    zscore_window = params.get("zscore_window", 60)
    
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
    
    def calculate_zscore(values):
        period = min(zscore_window, len(values))
        if period < 10:
            return 0.0
        recent = np.array(values[-period:])
        mean = np.mean(recent)
        std = np.std(recent)
        return (values[-1] - mean) / std if std > 0 else 0.0
    
    def calculate_volume_zscore():
        period = min(zscore_window, len(prev_volumes))
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
        
        cvd_zscore = calculate_zscore(prev_cvds)
        volume_zscore = calculate_volume_zscore()
        
        features = {
            "close": bar["close"],
            "high": bar["high"],
            "low": bar["low"],
            "volume": bar["volume"],
            "close_prices": prev_closes,
            "volumes": prev_volumes,
            "symbol": "BTCUSDT",
            "timestamp": bar["timestamp"],
            "cvd": cvd,
            "cvd_zscore": cvd_zscore,
            "volume_zscore": volume_zscore,
        }
        
        if len(prev_volumes) > 24:
            current_vol = prev_volumes[-1]
            avg_vol = np.mean(prev_volumes[-25:-1]) if len(prev_volumes) > 25 else np.mean(prev_volumes)
            features["volume_ratio"] = current_vol / avg_vol if avg_vol > 0 else 1.0
        
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
            if signal_dict:
                signal_type = signal_dict.get("signal_type", "")
                if signal_type in ["buy", "long"] and not in_position:
                    entry_price = prev_closes[-1] * (1 + slippage)
                    in_position = True
                    position_type = "long"
                    signal_count += 1
                    trades.append({"entry_price": entry_price, "entry_equity": equity, "pnl": 0})
                elif signal_type in ["sell", "short"] and not in_position:
                    entry_price = prev_closes[-1] * (1 - slippage)
                    in_position = True
                    position_type = "short"
                    signal_count += 1
                    trades.append({"entry_price": entry_price, "entry_equity": equity, "pnl": 0})
                elif signal_type in ["sell", "exit", "close"] and in_position:
                    exit_price = prev_closes[-1] * (1 - slippage)
                    if position_type == "long":
                        price_return = (exit_price - entry_price) / entry_price
                    else:
                        price_return = (entry_price - exit_price) / entry_price
                    margin = equity * position_size
                    pnl = margin * price_return * leverage
                    equity = equity + pnl
                    trades[-1]["pnl"] = pnl
                    in_position = False
        except:
            pass
    
    if in_position and prev_closes:
        exit_price = prev_closes[-1] * (1 - slippage)
        if position_type == "long":
            price_return = (exit_price - entry_price) / entry_price
        else:
            price_return = (entry_price - exit_price) / entry_price
        margin = equity * position_size
        pnl = margin * price_return * leverage
        equity = equity + pnl
        trades[-1]["pnl"] = pnl
    
    total_trades = len(trades)
    total_return = (equity - initial_capital) / initial_capital * 100
    
    if total_trades == 0:
        return {
            "strategy": strategy_id,
            "signals": signal_count,
            "trades": 0,
            "return": 0,
            "sharpe": 0,
            "win_rate": 0,
            "profit_factor": 0,
        }
    
    winning = [t for t in trades if t["pnl"] > 0]
    win_rate = len(winning) / total_trades * 100
    gross_profit = sum(t["pnl"] for t in winning)
    gross_loss = abs(sum(t["pnl"] for t in trades if t["pnl"] <= 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    returns = [t["pnl"] for t in trades]
    if len(returns) > 1 and np.std(returns) > 0:
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(len(returns))
    else:
        sharpe = 0
    
    return {
        "strategy": strategy_id,
        "signals": signal_count,
        "trades": total_trades,
        "return": total_return,
        "sharpe": sharpe,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
    }

def main():
    print("=" * 80)
    print("批量验证：不需要OI数据的策略（CPU加速）")
    print("=" * 80)
    
    print("\n加载数据...")
    bars_2022 = load_data(2022, 50000)
    bars_2023 = load_data(2023, 50000)
    bars_2024 = load_data(2024, 50000)
    
    # 准备任务
    tasks = []
    for strategy_id in STRATEGIES_TO_TEST:
        params = BEST_PARAMS.get(strategy_id, {})
        tasks.append((strategy_id, params, bars_2022))
        tasks.append((strategy_id, params, bars_2023))
        tasks.append((strategy_id, params, bars_2024))
    
    max_workers = min(get_default_workers(), 16)
    print(f"\n准备运行 {len(tasks)} 个任务（每个策略2022/2023/2024各一年）")
    print(f"使用 {max_workers} 个CPU核心\n")

    executor = CPUExecutor(executor_type="process", max_workers=max_workers)
    wrapped_tasks = [(task,) for task in tasks]
    results_raw = executor.execute(run_single_backtest, wrapped_tasks)
    results = []
    for r in results_raw:
        if r.error is None:
            results.append(r.result)
    
    # 整理结果
    results_by_year = {}
    for result in results:
        strategy_id = result["strategy"]
        if strategy_id not in results_by_year:
            results_by_year[strategy_id] = []
        results_by_year[strategy_id].append(result)
    
    # 输出汇总
    print("\n" + "=" * 100)
    print(f"{'Strategy':<30} {'Year':<8} {'Trades':>8} {'Return':>10} {'Sharpe':>10} {'Win%':>8} {'PF':>8}")
    print("=" * 100)
    
    all_results = []
    for strategy_id in STRATEGIES_TO_TEST:
        if strategy_id in results_by_year:
            year_results = results_by_year[strategy_id]
            year_results.sort(key=lambda x: x.get("trades", 0), reverse=True)
            
            for i, result in enumerate(year_results):
                year = 2022 + i
                print(f"{strategy_id:<30} {year:<8} "
                      f"{result.get('trades', 0):>8} "
                      f"{result.get('return', 0):>9.2f}% "
                      f"{result.get('sharpe', 0):>9.2f} "
                      f"{result.get('win_rate', 0):>7.1f}% "
                      f"{result.get('profit_factor', 0):>8.2f}")
                
                all_results.append({
                    "strategy": strategy_id,
                    "year": year,
                    **result
                })
    
    # 最佳策略排名（按平均夏普）
    print("\n" + "=" * 100)
    print("策略排行榜（按平均夏普排序，至少有一年有交易）")
    print("=" * 100)
    
    strategy_avg = {}
    for strategy_id in STRATEGIES_TO_TEST:
        if strategy_id in results_by_year:
            year_results = results_by_year[strategy_id]
            sharpes = [r.get("sharpe", 0) for r in year_results if r.get("trades", 0) > 0]
            if sharpes:
                avg_sharpe = np.mean(sharpes)
                avg_return = np.mean([r.get("return", 0) for r in year_results if r.get("trades", 0) > 0])
                total_trades = sum(r.get("trades", 0) for r in year_results)
                strategy_avg[strategy_id] = (avg_sharpe, avg_return, total_trades)
    
    sorted_strategies = sorted(strategy_avg.items(), key=lambda x: x[1][0], reverse=True)
    
    print(f"{'Rank':<5} {'Strategy':<30} {'Avg Sharpe':>12} {'Avg Return':>12} {'Total Trades':>12}")
    print("-" * 100)
    
    for i, (strategy_id, (avg_sharpe, avg_return, total_trades)) in enumerate(sorted_strategies):
        print(f"{i+1:<5} {strategy_id:<30} "
              f"{avg_sharpe:>12.2f} "
              f"{avg_return:>11.2f}% "
              f"{total_trades:>12}")

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
