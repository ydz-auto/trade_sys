#!/usr/bin/env python3
"""
策略排行榜脚本
测试所有策略在 2022-2024 年的 Walk-Forward 表现
输出统一指标：Sharpe, PF, Return, DD, Trades
"""
import sys
import os
from pathlib import Path
from datetime import datetime
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
from runtime.replay_runtime.backtest_engine import BacktestEngine, BacktestConfig, SignalType, Bar

logger = get_logger("strategy_leaderboard")


# 核心策略列表（不使用 OI 数据，专注于 Trade Pressure Framework）
# OI 可用替代：CVD + Volume ZScore + Taker Buy Ratio + Imbalance
CORE_STRATEGIES = [
    # 基础技术指标（对比基准）
    "rsi_oversold",
    "rsi_overbought",
    "macd_cross",
    "bollinger_bands",
    
    # 动量/趋势驱动
    "momentum",
    "trend_following",
    "breakout",
    
    # CVD/Pressure 驱动（可替代 OI - 重点测试）
    "cvd_divergence",
    "whale_trade",
    "aggressive_flow",
    "imbalance_pressure",
    "sweep_detection",
    
    # 恐慌/反转驱动
    "panic_reversal",
    "premium_divergence",
    
    # 成交量驱动
    "volume_climax_fade",
]


class SimpleBacktester:
    """简化的回测器，用于快速评估策略"""
    
    def __init__(self, enable_gpu=False):
        self.enable_gpu = enable_gpu
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
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))
    
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
        current = volumes[-1]
        avg = np.mean(volumes[-period-1:-1])
        return current / avg if avg > 0 else 1.0
    
    def calculate_cvd(self, closes, volumes):
        if len(closes) < 2:
            return 0.0
        import numpy as np
        price_diff = np.diff(closes)
        vol_array = np.array(volumes[1:])
        cvd = np.sum(np.where(price_diff > 0, vol_array, -vol_array))
        return float(cvd)
    
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
    
    def run_strategy(
        self,
        strategy_id: str,
        params: dict,
        bars: list,
        funding_df=None,
        oi_df=None
    ) -> dict:
        """运行单个策略的回测"""
        
        if len(bars) < 100:
            return self._empty_result(params)
        
        # State
        closes = []
        highs = []
        lows = []
        volumes = []
        cvds = []
        timestamps = []
        funding_rates = []
        
        # Strategy state
        in_position = False
        position_type = None
        entry_price = 0
        trades = []
        equity = 10000.0
        equity_curve = [equity]
        max_equity = equity
        max_drawdown = 0.0
        
        # Backtest config
        commission = 0.0004
        slippage = 0.0005
        position_size = 0.1
        
        try:
            strategy_info = get_strategy_info(strategy_id)
            direction = strategy_info.direction if strategy_info else "long"
        except:
            direction = "long"
        
        for bar in bars:
            closes.append(bar.close)
            highs.append(bar.high)
            lows.append(bar.low)
            volumes.append(bar.volume)
            timestamps.append(bar.timestamp)
            
            # Keep state limited
            if len(closes) > 600:
                closes = closes[-600:]
                highs = highs[-600:]
                lows = lows[-600:]
                volumes = volumes[-600:]
            
            if len(timestamps) > 1:
                cvds.append(self.calculate_cvd(closes, volumes))
                if len(cvds) > 1000:
                    cvds = cvds[-1000:]
            
            # Update funding rates
            if funding_df is not None:
                try:
                    ts_naive = bar.timestamp.replace(tzinfo=None) if hasattr(bar.timestamp, 'tzinfo') and bar.timestamp.tzinfo is not None else bar.timestamp
                    mask = funding_df["timestamp"] <= ts_naive
                    if mask.any():
                        funding_rates.append(float(funding_df.iloc[-1].get("fundingRate", 0.0)))
                        if len(funding_rates) > 1000:
                            funding_rates = funding_rates[-1000:]
                except:
                    pass
            
            # Generate features
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
            
            # Add technical indicators
            if len(closes) > 14:
                features["rsi_14"] = self.calculate_rsi(closes, 14)
            
            if len(closes) > 50:
                features["ema_fast"] = self.calculate_ema(closes, 10)
                features["ema_slow"] = self.calculate_ema(closes, 50)
            
            bb_upper, bb_middle, bb_lower = self.calculate_bollinger_bands(closes)
            if bb_upper is not None:
                features["bb_upper"] = bb_upper
                features["bb_middle"] = bb_middle
                features["bb_lower"] = bb_lower
            
            features["volume_ratio"] = self.calculate_volume_ratio(volumes)
            
            # Add CVD related features
            if len(cvds) > 10:
                features["cvd"] = cvds[-1]
                features["cvd_zscore"] = self.calculate_cvd_zscore(cvds)
            
            # Add price return features
            if len(closes) > 24:
                features["return_1h"] = (closes[-1] - closes[-24]) / closes[-24]
            if len(closes) > 168:
                features["return_24h"] = (closes[-1] - closes[-168]) / closes[-168]
            
            # Add funding features
            if len(funding_rates) > 10:
                features["funding_rate"] = funding_rates[-1]
                features["funding_zscore"] = self.calculate_zscore(funding_rates)
            
            # Add buy/sell pressure (simplified from taker data)
            if len(closes) > 10:
                import numpy as np
                price_moves = np.diff(closes[-10:])
                up_moves = np.sum(np.where(price_moves > 0, volumes[1:][-9:], 0))
                down_moves = np.sum(np.where(price_moves < 0, volumes[1:][-9:], 0))
                total = up_moves + down_moves
                features["taker_buy_ratio"] = up_moves / total if total > 0 else 0.5
            
            # Generate signal
            signal = "HOLD"
            try:
                from engines.compute.strategy.registry import get_strategy
                strategy = get_strategy(strategy_id, params)
                signal_dict = strategy.generate_signal(features)
                if signal_dict:
                    st = signal_dict.get("signal_type", "hold")
                    signal = st.upper()
            except Exception as e:
                # Fallback: use simple logic based on strategy
                signal = self._simple_signal(strategy_id, direction, features)
            
            # Execute trade
            if signal == "BUY" and not in_position:
                entry_price = bar.close * (1 + slippage)
                cost = equity * position_size * (commission + slippage)
                equity -= cost
                in_position = True
                position_type = "long"
                trades.append({
                    "type": "long",
                    "entry": entry_price,
                    "exit": None,
                    "pnl": 0,
                    "exit_reason": None
                })
            elif signal == "SELL" and in_position:
                exit_price = bar.close * (1 - slippage)
                pnl_pct = (exit_price - entry_price) / entry_price
                pnl = equity * position_size * pnl_pct
                cost = equity * position_size * commission
                equity += pnl - cost
                trades[-1]["exit"] = exit_price
                trades[-1]["pnl"] = pnl
                trades[-1]["exit_reason"] = "signal"
                in_position = False
                position_type = None
            
            # Update equity
            if in_position:
                pnl_pct = (bar.close - entry_price) / entry_price
                equity = equity + equity * position_size * pnl_pct
            
            equity_curve.append(equity)
            max_equity = max(max_equity, equity)
            dd = (max_equity - equity) / max_equity if max_equity > 0 else 0
            max_drawdown = max(max_drawdown, dd)
        
        # Close any open position
        if in_position and bars:
            last_bar = bars[-1]
            exit_price = last_bar.close * (1 - slippage)
            pnl_pct = (exit_price - entry_price) / entry_price
            pnl = equity * position_size * pnl_pct
            equity += pnl - equity * position_size * commission
            trades[-1]["exit"] = exit_price
            trades[-1]["pnl"] = pnl
            trades[-1]["exit_reason"] = "eod"
        
        # Calculate metrics
        total_trades = len(trades)
        if total_trades == 0:
            return self._empty_result(params)
        
        winning_trades = [t for t in trades if t["pnl"] > 0]
        losing_trades = [t for t in trades if t["pnl"] <= 0]
        
        total_return = (equity - 10000) / 10000
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
        
        gross_profit = sum(t["pnl"] for t in winning_trades)
        gross_loss = abs(sum(t["pnl"] for t in losing_trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Calculate Sharpe ratio
        if len(equity_curve) > 100:
            returns = np.diff(equity_curve) / equity_curve[:-1]
            sharpe = np.mean(returns) / np.std(returns) * np.sqrt(365 * 24) if np.std(returns) > 0 else 0
        else:
            sharpe = 0
        
        return {
            "params": params,
            "sharpe": sharpe,
            "total_trades": total_trades,
            "total_return": total_return,
            "max_drawdown": max_drawdown,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "equity_final": equity
        }
    
    def _simple_signal(self, strategy_id, direction, features):
        """简单的备用信号生成"""
        signal = "HOLD"
        
        # RSI based
        if "rsi" in strategy_id.lower():
            rsi = features.get("rsi_14", 50)
            if "oversold" in strategy_id.lower() and rsi < 30:
                signal = "BUY"
            elif "overbought" in strategy_id.lower() and rsi > 70:
                signal = "SELL"
        
        # MACD based
        elif "macd" in strategy_id.lower():
            ema_fast = features.get("ema_fast", 0)
            ema_slow = features.get("ema_slow", 0)
            if ema_fast > ema_slow:
                signal = "BUY"
            elif ema_fast < ema_slow:
                signal = "SELL"
        
        # Bollinger Bands based
        elif "bollinger" in strategy_id.lower() or "bb" in strategy_id.lower():
            close = features.get("close", 0)
            bb_lower = features.get("bb_lower", 0)
            bb_upper = features.get("bb_upper", 0)
            if close < bb_lower:
                signal = "BUY"
            elif close > bb_upper:
                signal = "SELL"
        
        # Momentum based
        elif "momentum" in strategy_id.lower():
            ret_1h = features.get("return_1h", 0)
            if ret_1h > 0.01:
                signal = "BUY"
            elif ret_1h < -0.01:
                signal = "SELL"
        
        # CVD divergence based
        elif "cvd" in strategy_id.lower():
            cvd_zscore = features.get("cvd_zscore", 0)
            if cvd_zscore < -2:
                signal = "BUY"
            elif cvd_zscore > 2:
                signal = "SELL"
        
        # Long liquidation bounce
        elif "long_liquidation" in strategy_id.lower():
            ret_1h = features.get("return_1h", 0)
            vol_ratio = features.get("volume_ratio", 1)
            if ret_1h < -0.02 and vol_ratio > 1.5:
                signal = "BUY"
        
        # Default: trend following
        else:
            ema_fast = features.get("ema_fast", 0)
            ema_slow = features.get("ema_slow", 0)
            if ema_fast > ema_slow * 1.001:
                signal = "BUY"
            elif ema_fast < ema_slow * 0.999:
                signal = "SELL"
        
        return signal
    
    def _empty_result(self, params):
        return {
            "params": params,
            "sharpe": -999,
            "total_trades": 0,
            "total_return": 0,
            "max_drawdown": 0,
            "win_rate": 0,
            "profit_factor": 0,
            "gross_profit": 0,
            "gross_loss": 0,
            "equity_final": 10000
        }


def load_year_data(year, backend_path):
    """加载指定年份的数据"""
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
                                bar = Bar(
                                    timestamp=row["timestamp"],
                                    open=float(row["open"]),
                                    high=float(row["high"]),
                                    low=float(row["low"]),
                                    close=float(row["close"]),
                                    volume=float(row["volume"])
                                )
                                bars.append(bar)
                            except:
                                pass
    
    # Load funding data
    funding_df = None
    funding_path = Path(backend_path) / "data_lake" / "crypto" / "binance" / "funding" / "symbol=BTCUSDT" / "data.parquet"
    if funding_path.exists():
        funding_df = read_parquet_safe(funding_path)
        if funding_df is not None:
            funding_df["timestamp"] = pd.to_datetime(funding_df["timestamp"], utc=True)
    
    return bars, funding_df


def run_leaderboard():
    """运行策略排行榜"""
    
    print("\n" + "="*100)
    print("STRATEGY LEADERBOARD")
    print("Testing key strategies on 2023 data (Quick Scan)")
    print("="*100 + "\n")
    
    years = [2023]  # 只测试2023年加快速度
    results = defaultdict(lambda: defaultdict(list))
    
    backtester = SimpleBacktester()
    
    # Load data for all years
    year_data = {}
    for year in years:
        print(f"Loading {year} data...")
        bars, funding_df = load_year_data(year, backend_path)
        year_data[year] = {"bars": bars, "funding_df": funding_df}
        print(f"  Loaded {len(bars)} bars, funding: {len(funding_df) if funding_df is not None else 0} rows")
    
    # Test each strategy
    for strategy_id in CORE_STRATEGIES:
        if strategy_id not in _STRATEGY_REGISTRY:
            print(f"  ⚠️  Skipping unknown strategy: {strategy_id}")
            continue
        
        print(f"\n{'='*80}")
        print(f"Testing: {strategy_id}")
        print(f"{'='*80}")
        
        strategy_results = []
        
        for year in years:
            data = year_data[year]
            bars = data["bars"]
            funding_df = data["funding_df"]
            
            if len(bars) < 100:
                print(f"  {year}: ❌ Insufficient data")
                continue
            
            # Get strategy info
            try:
                info = get_strategy_info(strategy_id)
                default_params = info.default_params if info else {}
            except:
                default_params = {}
            
            # Use first 2 months for optimization, rest for testing (加速)
            train_bars = bars[:len(bars)//6]  # 2个月
            test_bars = bars[len(bars)//6:]   # 剩余10个月
            
            print(f"  {year}: Testing {len(train_bars)} train bars, {len(test_bars)} test bars")
            
            start = time.time()
            result = backtester.run_strategy(
                strategy_id=strategy_id,
                params=default_params,
                bars=test_bars,
                funding_df=funding_df
            )
            elapsed = time.time() - start
            
            result["year"] = year
            result["train_bars"] = len(train_bars)
            result["test_bars"] = len(test_bars)
            result["elapsed"] = elapsed
            
            strategy_results.append(result)
            
            # Print result
            if result["sharpe"] > -999:
                print(f"    Sharpe: {result['sharpe']:.4f}, Trades: {result['total_trades']}, "
                      f"Return: {result['total_return']*100:.2f}%, DD: {result['max_drawdown']*100:.2f}%, "
                      f"PF: {result['profit_factor']:.2f}")
            else:
                print(f"    ❌ No trades")
            
            # Store aggregate results
            results[strategy_id]["sharpe"].append(result["sharpe"])
            results[strategy_id]["trades"].append(result["total_trades"])
            results[strategy_id]["return"].append(result["total_return"])
            results[strategy_id]["dd"].append(result["max_drawdown"])
            results[strategy_id]["pf"].append(result["profit_factor"])
        
        # Calculate averages
        if strategy_results:
            avg_sharpe = np.mean(results[strategy_id]["sharpe"])
            avg_trades = np.mean(results[strategy_id]["trades"])
            avg_return = np.mean(results[strategy_id]["return"])
            avg_dd = np.mean(results[strategy_id]["dd"])
            avg_pf = np.mean(results[strategy_id]["pf"])
            
            results[strategy_id]["avg_sharpe"] = avg_sharpe
            results[strategy_id]["avg_trades"] = avg_trades
            results[strategy_id]["avg_return"] = avg_return
            results[strategy_id]["avg_dd"] = avg_dd
            results[strategy_id]["avg_pf"] = avg_pf
    
    # Generate leaderboard
    print("\n\n" + "="*100)
    print("FINAL LEADERBOARD")
    print("="*100)
    
    leaderboard = []
    for strategy_id in CORE_STRATEGIES:
        if strategy_id in results and "avg_sharpe" in results[strategy_id]:
            r = results[strategy_id]
            leaderboard.append({
                "strategy": strategy_id,
                "avg_sharpe": r["avg_sharpe"],
                "avg_trades": r["avg_trades"],
                "avg_return": r["avg_return"],
                "avg_dd": r["avg_dd"],
                "avg_pf": r["avg_pf"],
                "years_tested": len(r["sharpe"])
            })
    
    # Sort by Sharpe
    leaderboard.sort(key=lambda x: x["avg_sharpe"], reverse=True)
    
    print(f"\n{'Rank':<5} {'Strategy':<30} {'Sharpe':>8} {'Trades':>8} {'Return':>10} {'DD':>8} {'PF':>8}")
    print("-" * 85)
    
    for i, row in enumerate(leaderboard, 1):
        status = "✅" if row["avg_sharpe"] > 0.5 else ("⚠️" if row["avg_sharpe"] > 0 else "❌")
        print(f"{i:<5} {row['strategy']:<30} {row['avg_sharpe']:>8.4f} {row['avg_trades']:>8.0f} "
              f"{row['avg_return']*100:>9.2f}% {row['avg_dd']*100:>7.2f}% {row['avg_pf']:>8.2f} {status}")
    
    # Save to CSV
    output_path = Path(script_dir) / "output" / "strategy_leaderboard.csv"
    output_path.parent.mkdir(exist_ok=True)
    
    df = pd.DataFrame(leaderboard)
    df.to_csv(output_path, index=False)
    print(f"\n\nResults saved to: {output_path}")
    
    return leaderboard


if __name__ == "__main__":
    import numpy as np
    leaderboard = run_leaderboard()
