#!/usr/bin/env python3
"""
快速策略扫描脚本
使用较少数据快速评估策略潜力
"""
import sys
import os
from pathlib import Path
import pandas as pd
from collections import defaultdict
import time

# Add backend to path
script_dir = os.path.dirname(os.path.abspath(__file__))
backend_path = os.path.abspath(os.path.join(script_dir, '..', 'backend'))
sys.path.insert(0, backend_path)

from infrastructure.logging import get_logger
from infrastructure.storage.parquet_reader import read_parquet_safe
from engines.compute.strategy.registry import get_strategy_info, _STRATEGY_REGISTRY
from runtimes.replay_runtime.backtest_engine import Bar

logger = get_logger("quick_scan")


# 核心策略列表
CORE_STRATEGIES = [
    "rsi_oversold",
    "rsi_overbought",
    "macd_cross",
    "bollinger_bands",
    "momentum",
    "trend_following",
    "breakout",
    "cvd_divergence",
    "whale_trade",
    "aggressive_flow",
    "imbalance_pressure",
    "sweep_detection",
    "panic_reversal",
    "premium_divergence",
    "volume_climax_fade",
]


class QuickBacktester:
    """轻量级回测器"""
    
    def __init__(self):
        self.results = []
    
    def calculate_rsi(self, prices, period=14):
        if len(prices) < period + 1:
            return 50.0
        import numpy as np
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        if avg_loss == 0:
            return 100.0
        return 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))
    
    def calculate_ema(self, prices, period):
        if len(prices) < period:
            return prices[-1] if prices else 0
        import numpy as np
        weights = np.exp(np.linspace(-1., 0., period))
        weights /= weights.sum()
        return float(np.convolve(prices, weights, mode='valid')[-1])
    
    def calculate_bollinger_bands(self, prices, period=20):
        import numpy as np
        if len(prices) < period:
            return None, None, None
        recent = prices[-period:]
        sma = np.mean(recent)
        std = np.std(recent)
        return sma + 2 * std, sma, sma - 2 * std
    
    def calculate_volume_ratio(self, volumes, period=24):
        if len(volumes) < period + 1:
            return 1.0
        import numpy as np
        return volumes[-1] / np.mean(volumes[-period-1:-1]) if np.mean(volumes[-period-1:-1]) > 0 else 1.0
    
    def calculate_cvd_zscore(self, cvds, period=240):
        if len(cvds) < period:
            return 0.0
        import numpy as np
        recent = np.array(cvds[-period:])
        mean = np.mean(recent)
        std = np.std(recent)
        return (cvds[-1] - mean) / std if std > 0 else 0.0
    
    def calculate_zscore(self, values, period=240):
        if len(values) < period:
            return 0.0
        import numpy as np
        recent = np.array(values[-period:])
        mean = np.mean(recent)
        std = np.std(recent)
        return (values[-1] - mean) / std if std > 0 else 0.0
    
    def run_strategy(self, strategy_id, params, bars):
        if len(bars) < 200:
            return self._empty_result()
        
        closes = []
        highs = []
        lows = []
        volumes = []
        cvds = []
        
        equity = 10000.0
        position_size = 0.1
        commission = 0.0004
        slippage = 0.0005
        max_equity = equity
        max_drawdown = 0.0
        
        in_position = False
        entry_price = 0
        trades = []
        
        for bar in bars:
            closes.append(bar.close)
            highs.append(bar.high)
            lows.append(bar.low)
            volumes.append(bar.volume)
            
            if len(closes) > 600:
                closes, highs, lows, volumes = closes[-600:], highs[-600:], lows[-600:], volumes[-600:]
            
            # Calculate CVD
            if len(closes) > 2:
                import numpy as np
                price_diff = np.diff(closes)
                vol_array = np.array(volumes[1:])
                cvd = np.sum(np.where(price_diff > 0, vol_array, -vol_array))
                cvds.append(cvd)
                if len(cvds) > 1000:
                    cvds = cvds[-1000:]
            
            # Build features
            features = {
                "close": bar.close,
                "high": bar.high,
                "low": bar.low,
                "volume": bar.volume,
                "close_prices": closes,
                "high_prices": highs,
                "low_prices": lows,
                "volumes": volumes,
                "symbol": "BTCUSDT",
                "timestamp": bar.timestamp
            }
            
            if len(closes) > 14:
                features["rsi_14"] = self.calculate_rsi(closes)
            
            if len(closes) > 50:
                features["ema_fast"] = self.calculate_ema(closes, 10)
                features["ema_slow"] = self.calculate_ema(closes, 50)
            
            bb_upper, bb_middle, bb_lower = self.calculate_bollinger_bands(closes)
            if bb_upper:
                features["bb_upper"] = bb_upper
                features["bb_middle"] = bb_middle
                features["bb_lower"] = bb_lower
            
            features["volume_ratio"] = self.calculate_volume_ratio(volumes)
            
            if len(cvds) > 10:
                features["cvd"] = cvds[-1]
                features["cvd_zscore"] = self.calculate_cvd_zscore(cvds)
            
            if len(closes) > 24:
                features["return_1h"] = (closes[-1] - closes[-24]) / closes[-24]
            
            # Generate signal
            signal = self._simple_signal(strategy_id, features)
            
            # Execute
            if signal == "BUY" and not in_position:
                entry_price = bar.close * (1 + slippage)
                equity -= equity * position_size * (commission + slippage)
                in_position = True
                trades.append({"type": "long", "entry": entry_price, "pnl": 0})
            elif signal == "SELL" and in_position:
                exit_price = bar.close * (1 - slippage)
                pnl = equity * position_size * (exit_price - entry_price) / entry_price
                equity += pnl - equity * position_size * commission
                trades[-1]["exit"] = exit_price
                trades[-1]["pnl"] = pnl
                in_position = False
            
            if in_position:
                pnl = equity * position_size * (bar.close - entry_price) / entry_price
                equity += pnl
            
            max_equity = max(max_equity, equity)
            max_drawdown = max(max_drawdown, (max_equity - equity) / max_equity)
        
        # Close position
        if in_position and bars:
            exit_price = bars[-1].close * (1 - slippage)
            pnl = equity * position_size * (exit_price - entry_price) / entry_price
            equity += pnl - equity * position_size * commission
            trades[-1]["exit"] = exit_price
            trades[-1]["pnl"] = pnl
        
        total_trades = len(trades)
        if total_trades == 0:
            return self._empty_result()
        
        winning = [t for t in trades if t["pnl"] > 0]
        losing = [t for t in trades if t["pnl"] <= 0]
        
        total_return = (equity - 10000) / 10000
        win_rate = len(winning) / total_trades
        gross_profit = sum(t["pnl"] for t in winning)
        gross_loss = abs(sum(t["pnl"] for t in losing))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        return {
            "sharpe": total_return / max_drawdown if max_drawdown > 0 else 0,
            "total_trades": total_trades,
            "total_return": total_return,
            "max_drawdown": max_drawdown,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
        }
    
    def _simple_signal(self, strategy_id, features):
        signal = "HOLD"
        
        if "rsi" in strategy_id.lower():
            rsi = features.get("rsi_14", 50)
            if "oversold" in strategy_id.lower() and rsi < 30:
                signal = "BUY"
            elif "overbought" in strategy_id.lower() and rsi > 70:
                signal = "SELL"
        
        elif "macd" in strategy_id.lower():
            ema_fast = features.get("ema_fast", 0)
            ema_slow = features.get("ema_slow", 0)
            if ema_fast > ema_slow * 1.001:
                signal = "BUY"
            elif ema_fast < ema_slow * 0.999:
                signal = "SELL"
        
        elif "bollinger" in strategy_id.lower() or "bb" in strategy_id.lower():
            close = features.get("close", 0)
            if close < features.get("bb_lower", 0):
                signal = "BUY"
            elif close > features.get("bb_upper", 0):
                signal = "SELL"
        
        elif "momentum" in strategy_id.lower():
            ret = features.get("return_1h", 0)
            if ret > 0.01:
                signal = "BUY"
            elif ret < -0.01:
                signal = "SELL"
        
        elif "cvd" in strategy_id.lower():
            cvd_z = features.get("cvd_zscore", 0)
            if cvd_z < -2:
                signal = "BUY"
            elif cvd_z > 2:
                signal = "SELL"
        
        elif "whale" in strategy_id.lower():
            vol_r = features.get("volume_ratio", 1)
            if vol_r > 2:
                signal = "BUY"
        
        elif "aggressive" in strategy_id.lower():
            cvd_z = features.get("cvd_zscore", 0)
            vol_r = features.get("volume_ratio", 1)
            if abs(cvd_z) > 1.5 and vol_r > 1.5:
                signal = "BUY" if cvd_z < 0 else "SELL"
        
        elif "imbalance" in strategy_id.lower():
            cvd_z = features.get("cvd_zscore", 0)
            if abs(cvd_z) > 1.5:
                signal = "BUY" if cvd_z < 0 else "SELL"
        
        elif "sweep" in strategy_id.lower():
            close = features.get("close", 0)
            bb_lower = features.get("bb_lower", 0)
            if close < bb_lower * 1.01:
                signal = "BUY"
        
        elif "panic" in strategy_id.lower():
            close = features.get("close", 0)
            bb_lower = features.get("bb_lower", 0)
            if close < bb_lower:
                signal = "BUY"
        
        elif "premium" in strategy_id.lower():
            cvd_z = features.get("cvd_zscore", 0)
            if cvd_z < -1.5:
                signal = "BUY"
        
        elif "volume_climax" in strategy_id.lower():
            vol_r = features.get("volume_ratio", 1)
            ret = features.get("return_1h", 0)
            if vol_r > 3 and abs(ret) > 0.03:
                signal = "SELL" if ret > 0 else "BUY"
        
        elif "breakout" in strategy_id.lower():
            close = features.get("close", 0)
            bb_upper = features.get("bb_upper", 0)
            if close > bb_upper:
                signal = "BUY"
        
        elif "trend" in strategy_id.lower():
            ema_fast = features.get("ema_fast", 0)
            ema_slow = features.get("ema_slow", 0)
            if ema_fast > ema_slow:
                signal = "BUY"
        
        else:
            # Default: EMA crossover
            ema_fast = features.get("ema_fast", 0)
            ema_slow = features.get("ema_slow", 0)
            if ema_fast > ema_slow * 1.001:
                signal = "BUY"
            elif ema_fast < ema_slow * 0.999:
                signal = "SELL"
        
        return signal
    
    def _empty_result(self):
        return {
            "sharpe": -999,
            "total_trades": 0,
            "total_return": 0,
            "max_drawdown": 0,
            "win_rate": 0,
            "profit_factor": 0,
        }


def load_data():
    """加载2023年数据（前10万条）"""
    data_path = Path(backend_path) / "data_lake" / "crypto" / "binance" / "klines" / "symbol=BTCUSDT" / "year=2023"
    bars = []
    
    if data_path.exists():
        for month_dir in sorted(data_path.iterdir())[:4]:  # 只加载前4个月
            if month_dir.is_dir() and month_dir.name.startswith("month="):
                parquet_file = month_dir / "data.parquet"
                if parquet_file.exists():
                    df = read_parquet_safe(parquet_file)
                    if df is not None:
                        for _, row in df.iterrows():
                            try:
                                bar = Bar(
                                    timestamp=row["timestamp"],
                                    open=float(row["open"]),
                                    high=float(row["high"]),
                                    low=float(row["low"]),
                                    close=float(row["close"]),
                                    volume=float(row["volume"])
                                )
                                bars.append(bar)
                                if len(bars) >= 100000:  # 限制数据量
                                    break
                            except:
                                pass
                if len(bars) >= 100000:
                    break
    
    return bars


def run_scan():
    print("\n" + "="*100)
    print("QUICK STRATEGY SCAN")
    print("="*100)
    
    print("\nLoading data...")
    bars = load_data()
    print(f"Loaded {len(bars)} bars\n")
    
    if len(bars) < 1000:
        print("❌ Insufficient data!")
        return []
    
    backtester = QuickBacktester()
    results = []
    
    for strategy_id in CORE_STRATEGIES:
        if strategy_id not in _STRATEGY_REGISTRY:
            continue
        
        try:
            info = get_strategy_info(strategy_id)
            params = info.default_params if info else {}
        except:
            params = {}
        
        print(f"Testing {strategy_id}...", end=" ")
        start = time.time()
        
        result = backtester.run_strategy(strategy_id, params, bars)
        elapsed = time.time() - start
        
        result["strategy"] = strategy_id
        result["elapsed"] = elapsed
        results.append(result)
        
        if result["sharpe"] > -999:
            status = "✅" if result["sharpe"] > 0.5 else ("⚠️" if result["sharpe"] > 0 else "❌")
            print(f"Sharpe={result['sharpe']:.2f}, Trades={result['total_trades']}, "
                  f"Return={result['total_return']*100:.1f}%, PF={result['profit_factor']:.2f} {status}")
        else:
            print("❌ No trades")
    
    # Sort and display
    print("\n" + "="*100)
    print("FINAL RANKING (by Sharpe)")
    print("="*100)
    
    results.sort(key=lambda x: x["sharpe"], reverse=True)
    
    print(f"\n{'Rank':<5} {'Strategy':<25} {'Sharpe':>8} {'Trades':>8} {'Return':>10} {'DD':>8} {'PF':>8}")
    print("-" * 80)
    
    for i, r in enumerate(results, 1):
        status = "✅" if r["sharpe"] > 0.5 else ("⚠️" if r["sharpe"] > 0 else "❌")
        print(f"{i:<5} {r['strategy']:<25} {r['sharpe']:>8.2f} {r['total_trades']:>8} "
              f"{r['total_return']*100:>9.1f}% {r['max_drawdown']*100:>7.1f}% {r['profit_factor']:>8.2f} {status}")
    
    # Save results
    output_path = Path(script_dir) / "output" / "quick_scan_results.csv"
    output_path.parent.mkdir(exist_ok=True)
    df = pd.DataFrame(results)
    df.to_csv(output_path, index=False)
    print(f"\nResults saved to: {output_path}")
    
    return results


if __name__ == "__main__":
    results = run_scan()
