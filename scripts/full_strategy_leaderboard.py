#!/usr/bin/env python3
"""
完整的策略排行榜：测试所有不需要OI数据的策略（CPU加速）
包含完整的特征计算
"""
import sys
import os
from pathlib import Path
import multiprocessing
import numpy as np

script_dir = os.path.dirname(os.path.abspath(__file__))
backend_path = os.path.abspath(os.path.join(script_dir, '..', 'backend'))
sys.path.insert(0, backend_path)

from infrastructure.acceleration import CPUExecutor, get_default_workers
from infrastructure.storage.parquet_reader import read_parquet_safe
from engines.compute.strategy.registry import get_strategy, get_strategy_info, list_strategies

# 不需要OI数据的策略列表 - 从策略注册表中筛选
def get_non_oi_strategies():
    """获取不需要OI数据的策略"""
    non_oi_strategies = []
    for strategy_info in list_strategies():
        required_features = strategy_info.required_features
        # 排除需要OI数据的策略
        requires_oi = any('oi' in feature.lower() for feature in required_features)
        if not requires_oi:
            non_oi_strategies.append(strategy_info.strategy_id)
    return non_oi_strategies

STRATEGIES_TO_TEST = get_non_oi_strategies()
print(f"测试策略数量: {len(STRATEGIES_TO_TEST)}")

# 最佳参数
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


def calculate_rsi(prices, period=14):
    """计算RSI"""
    if len(prices) < period + 1:
        return 50.0
    
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_macd(prices, fast=12, slow=26, signal=9):
    """计算MACD"""
    if len(prices) < slow + signal:
        return 0.0, 0.0, 0.0
    
    # 简单EMA计算
    def ema(values, period):
        weights = np.exp(np.linspace(-1, 0, period))
        weights /= weights.sum()
        return np.convolve(values, weights, mode='valid')[-1] if len(values) >= period else values[-1]
    
    ema_fast = ema(np.array(prices[-slow:]), fast)
    ema_slow = ema(np.array(prices[-slow:]), slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema([macd_line], signal)  # 简化
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def calculate_sma(prices, period):
    """计算SMA"""
    if len(prices) < period:
        return prices[-1] if prices else 0
    return np.mean(prices[-period:])


def calculate_bollinger_bands(prices, period=20, std_dev=2):
    """计算布林带"""
    if len(prices) < period:
        return prices[-1], prices[-1], prices[-1]
    
    sma = np.mean(prices[-period:])
    std = np.std(prices[-period:])
    upper = sma + std_dev * std
    lower = sma - std_dev * std
    return upper, sma, lower


def load_data(year=2023, max_bars=50000):
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
    """单个策略的完整回测（包含所有特征）"""
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
    prev_opens = []
    prev_highs = []
    prev_lows = []
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
    
    zscore_window = params.get("zscore_window", 60)
    
    for bar in bars:
        prev_closes.append(bar["close"])
        prev_opens.append(bar["open"])
        prev_highs.append(bar["high"])
        prev_lows.append(bar["low"])
        prev_volumes.append(bar["volume"])
        
        # 限制历史数据长度
        if len(prev_closes) > 600:
            prev_closes = prev_closes[-600:]
            prev_opens = prev_opens[-600:]
            prev_highs = prev_highs[-600:]
            prev_lows = prev_lows[-600:]
            prev_volumes = prev_volumes[-600:]
        
        # 计算基础特征
        cvd = 0.0
        if len(prev_closes) >= 2:
            price_diff = np.diff(prev_closes[-2:])[0]
            cvd = prev_volumes[-1] if price_diff > 0 else -prev_volumes[-1]
        
        prev_cvds.append(cvd)
        if len(prev_cvds) > 1000:
            prev_cvds = prev_cvds[-1000:]
        
        # 计算所有策略需要的特征
        features = {
            "close": bar["close"],
            "open": bar["open"],
            "high": bar["high"],
            "low": bar["low"],
            "volume": bar["volume"],
            "close_prices": prev_closes,
            "volumes": prev_volumes,
            "symbol": "BTCUSDT",
            "timestamp": bar["timestamp"],
            "cvd": cvd,
        }
        
        # 计算技术指标
        if len(prev_closes) >= 14:
            features["rsi_14"] = calculate_rsi(prev_closes, 14)
        
        if len(prev_closes) >= 35:
            macd_line, signal_line, histogram = calculate_macd(prev_closes)
            features["macd"] = macd_line
            features["macd_signal"] = signal_line
        
        if len(prev_closes) >= 50:
            features["sma_10"] = calculate_sma(prev_closes, 10)
            features["sma_50"] = calculate_sma(prev_closes, 50)
            features["ema_10"] = calculate_sma(prev_closes, 10)  # 简化
            features["ema_50"] = calculate_sma(prev_closes, 50)  # 简化
        
        if len(prev_closes) >= 20:
            bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(prev_closes)
            features["bb_upper"] = bb_upper
            features["bb_middle"] = bb_middle
            features["bb_lower"] = bb_lower
        
        # 计算其他特征
        if len(prev_volumes) > 24:
            current_vol = prev_volumes[-1]
            avg_vol = np.mean(prev_volumes[-25:-1]) if len(prev_volumes) > 25 else np.mean(prev_volumes)
            features["volume_ratio"] = current_vol / avg_vol if avg_vol > 0 else 1.0
        
        if len(prev_closes) > 24:
            features["return_1h"] = (prev_closes[-1] - prev_closes[-24]) / prev_closes[-24]
        
        if len(prev_closes) > 96:
            features["return_4h"] = (prev_closes[-1] - prev_closes[-96]) / prev_closes[-96]
        
        # CVD ZScore
        if len(prev_cvds) >= zscore_window:
            recent_cvds = np.array(prev_cvds[-zscore_window:])
            cvd_mean = np.mean(recent_cvds)
            cvd_std = np.std(recent_cvds)
            features["cvd_zscore"] = (cvd - cvd_mean) / cvd_std if cvd_std > 0 else 0
        else:
            features["cvd_zscore"] = 0
        
        # Volume ZScore
        if len(prev_volumes) >= zscore_window:
            recent_vols = np.array(prev_volumes[-zscore_window:])
            vol_mean = np.mean(recent_vols)
            vol_std = np.std(recent_vols)
            features["volume_zscore"] = (prev_volumes[-1] - vol_mean) / vol_std if vol_std > 0 else 0
        else:
            features["volume_zscore"] = 0
        
        # 简单taker买卖比例
        if len(prev_closes) > 10:
            price_moves = np.diff(prev_closes[-10:])
            up_vol = np.sum(np.where(price_moves > 0, prev_volumes[-9:], 0))
            down_vol = np.sum(np.where(price_moves < 0, prev_volumes[-9:], 0))
            total = up_vol + down_vol
            features["taker_buy_ratio"] = up_vol / total if total > 0 else 0.5
        
        # 上影线比例
        if bar["close"] != 0:
            upper_shadow = bar["high"] - max(bar["open"], bar["close"])
            features["upper_shadow_ratio"] = upper_shadow / bar["close"]
        
        # 生成信号
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
        except Exception as e:
            pass
    
    # 平仓处理
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
    print("=" * 100)
    print("完整策略排行榜：不需要OI数据的策略（CPU加速）")
    print("=" * 100)
    
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
    
    # 输出详细结果
    print("\n" + "=" * 110)
    print(f"{'Strategy':<30} {'Year':<6} {'Trades':>8} {'Return':>10} {'Sharpe':>10} {'Win%':>8} {'PF':>8}")
    print("=" * 110)
    
    all_results = []
    for strategy_id in STRATEGIES_TO_TEST:
        if strategy_id in results_by_year:
            year_results = results_by_year[strategy_id]
            year_results.sort(key=lambda x: x.get("trades", 0), reverse=True)
            
            for i, result in enumerate(year_results):
                year = 2022 + i
                print(f"{strategy_id:<30} {year:<6} "
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
    
    # 最佳策略排名
    print("\n" + "=" * 110)
    print("策略排行榜（按平均夏普排序，至少有10笔交易）")
    print("=" * 110)
    
    strategy_avg = {}
    for strategy_id in STRATEGIES_TO_TEST:
        if strategy_id in results_by_year:
            year_results = results_by_year[strategy_id]
            valid_results = [r for r in year_results if r.get("trades", 0) >= 10]
            if valid_results:
                avg_sharpe = np.mean([r.get("sharpe", 0) for r in valid_results])
                avg_return = np.mean([r.get("return", 0) for r in valid_results])
                total_trades = sum(r.get("trades", 0) for r in valid_results)
                best_year = max(valid_results, key=lambda x: x.get("sharpe", 0))
                strategy_avg[strategy_id] = (avg_sharpe, avg_return, total_trades, best_year.get("year"))
    
    sorted_strategies = sorted(strategy_avg.items(), key=lambda x: x[1][0], reverse=True)
    
    print(f"{'Rank':<5} {'Strategy':<30} {'Avg Sharpe':>12} {'Avg Return':>12} {'Total Trades':>14} {'Best Year':>10}")
    print("-" * 110)
    
    for i, (strategy_id, (avg_sharpe, avg_return, total_trades, best_year)) in enumerate(sorted_strategies):
        print(f"{i+1:<5} {strategy_id:<30} "
              f"{avg_sharpe:>12.2f} "
              f"{avg_return:>11.2f}% "
              f"{total_trades:>14} "
              f"{best_year:>10}")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
