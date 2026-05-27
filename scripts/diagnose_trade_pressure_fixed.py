#!/usr/bin/env python3
"""
诊断脚本：测试 Trade Pressure Framework 策略（修复 Equity 更新逻辑）
"""
import sys
import os
from pathlib import Path

script_dir = os.path.dirname(os.path.abspath(__file__))
backend_path = os.path.abspath(os.path.join(script_dir, '..', 'backend'))
sys.path.insert(0, backend_path)

from infrastructure.storage.parquet_reader import read_parquet_safe
from engines.compute.strategy.registry import get_strategy, get_strategy_info
from runtime.replay_runtime.backtest_engine import Bar
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
                                bar = Bar(
                                    timestamp=row["timestamp"],
                                    open=float(row["open"]),
                                    high=float(row["high"]),
                                    low=float(row["low"]),
                                    close=float(row["close"]),
                                    volume=float(row["volume"])
                                )
                                bars.append(bar)
                                if len(bars) >= max_bars:
                                    break
                            except:
                                pass
                if len(bars) >= max_bars:
                    break
    
    print(f"Loaded {len(bars)} bars")
    return bars


class RealStrategyBacktester:
    def __init__(self, strategy_id, params=None):
        self.strategy_id = strategy_id
        self.strategy = get_strategy(strategy_id, params or {})
        
        self.prev_closes = []
        self.prev_volumes = []
        self.prev_cvds = []
        
        self.equity = 10000.0
        self.initial_capital = self.equity
        self.position_size = 0.1  # 10% 仓位（资金比例）
        self.leverage = 1.0
        self.commission = 0.0004
        self.slippage = 0.0005
        self.max_equity = self.equity
        self.max_drawdown = 0.0
        self.in_position = False
        self.position_type = None
        self.entry_price = 0
        self.trades = []
        
        self.signal_count = 0
        self.buy_signals = 0
        self.sell_signals = 0
        self.liquidation_count = 0
        
        self.cvd_zscore_values = []
    
    def calculate_cvd_from_history(self):
        if len(self.prev_closes) < 2:
            return 0.0
        price_diff = np.diff(self.prev_closes)
        vol_array = np.array(self.prev_volumes[1:])
        cvd = np.sum(np.where(price_diff > 0, vol_array, -vol_array))
        return float(cvd)
    
    def calculate_zscore(self, values, period=240):
        if len(values) < period:
            return 0.0
        recent = np.array(values[-period:])
        mean = np.mean(recent)
        std = np.std(recent)
        return (values[-1] - mean) / std if std > 0 else 0.0
    
    def calculate_volume_ratio(self, period=24):
        if len(self.prev_volumes) < period + 1:
            return 1.0
        current = self.prev_volumes[-1]
        avg = np.mean(self.prev_volumes[-period-1:-1])
        return current / avg if avg > 0 else 1.0
    
    def build_features(self, bar):
        features = {
            "close": bar.close,
            "high": bar.high,
            "low": bar.low,
            "volume": bar.volume,
            "close_prices": self.prev_closes + [bar.close],
            "volumes": self.prev_volumes + [bar.volume],
            "symbol": "BTCUSDT",
            "timestamp": bar.timestamp
        }
        
        features["volume_ratio"] = self.calculate_volume_ratio()
        
        if len(self.prev_cvds) > 10:
            features["cvd"] = self.prev_cvds[-1]
            features["cvd_zscore"] = self.calculate_zscore(self.prev_cvds)
            self.cvd_zscore_values.append(features["cvd_zscore"])
        
        if len(self.prev_closes) > 24:
            features["return_1h"] = (self.prev_closes[-1] - self.prev_closes[-24]) / self.prev_closes[-24]
        
        if len(self.prev_closes) > 10:
            price_moves = np.diff(self.prev_closes[-10:])
            up_vol = np.sum(np.where(price_moves > 0, self.prev_volumes[-9:], 0))
            down_vol = np.sum(np.where(price_moves < 0, self.prev_volumes[-9:], 0))
            total = up_vol + down_vol
            features["taker_buy_ratio"] = up_vol / total if total > 0 else 0.5
        
        return features
    
    def update_history(self, bar):
        self.prev_closes.append(bar.close)
        self.prev_volumes.append(bar.volume)
        
        if len(self.prev_closes) > 600:
            self.prev_closes = self.prev_closes[-600:]
            self.prev_volumes = self.prev_volumes[-600:]
        
        cvd = self.calculate_cvd_from_history()
        self.prev_cvds.append(cvd)
        if len(self.prev_cvds) > 1000:
            self.prev_cvds = self.prev_cvds[-1000:]
    
    def execute_signal(self, signal_type):
        if signal_type == "buy" and not self.in_position:
            self.entry_price = self.prev_closes[-1] * (1 + self.slippage)
            self.in_position = True
            self.position_type = "long"
            self.buy_signals += 1
            self.trades.append({
                "type": "long",
                "entry_time": len(self.prev_closes),
                "entry_price": self.entry_price,
                "entry_equity": self.equity,
                "exit_time": None,
                "exit_price": None,
                "pnl": None,
                "pnl_pct": None,
                "price_return_pct": None,
            })
            
        elif signal_type == "sell" and self.in_position:
            exit_price = self.prev_closes[-1] * (1 - self.slippage)
            self.sell_signals += 1
            
            # 计算价格回报
            if self.position_type == "long":
                price_return = (exit_price - self.entry_price) / self.entry_price
            else:
                price_return = (self.entry_price - exit_price) / self.entry_price
            
            # 计算 PnL（简单：equity_before + pnl，不重复乘
            margin = self.equity * self.position_size
            pnl = margin * price_return * self.leverage
            
            # 更新 equity
            equity_before = self.equity
            self.equity = equity_before + pnl
            
            self.trades[-1].update({
                "exit_time": len(self.prev_closes),
                "exit_price": exit_price,
                "exit_equity": self.equity,
                "pnl": pnl,
                "pnl_pct": (self.equity - self.trades[-1]["entry_equity"]) / self.trades[-1]["entry_equity"] * 100,
                "price_return_pct": price_return * 100,
            })
            
            self.in_position = False
            self.position_type = None
            
            # 检查异常
            if abs(self.trades[-1]["pnl_pct"]) > 10:
                print("⚠️ suspicious trade", self.trades[-1])
    
    def update_equity(self):
        if self.in_position and len(self.prev_closes) > 0:
            current_price = self.prev_closes[-1]
            if self.position_type == "long":
                unrealized_return = (current_price - self.entry_price) / self.entry_price
            else:
                unrealized_return = (self.entry_price - current_price) / self.entry_price
            margin = self.equity * self.position_size
            unrealized_pnl = margin * unrealized_return * self.leverage
            # 这里不要更新 equity，因为 unrealized pnl 不应该立即加到权益上
            # 只有平仓时才更新 equity
        
        self.max_equity = max(self.max_equity, self.equity)
        dd = (self.max_equity - self.equity) / self.max_equity if self.max_equity > 0 else 0
        self.max_drawdown = max(self.max_drawdown, dd)
    
    def run(self, bars):
        for bar in bars:
            self.update_history(bar)
            features = self.build_features(bar)
            
            try:
                signal_dict = self.strategy.generate_signal(features)
                if signal_dict:
                    self.signal_count += 1
                    self.execute_signal(signal_dict.get("signal_type", "hold"))
            except:
                pass
            
            self.update_equity()
        
        if self.in_position and self.prev_closes:
            exit_price = self.prev_closes[-1] * (1 - self.slippage)
            if self.position_type == "long":
                price_return = (exit_price - self.entry_price) / self.entry_price
            else:
                price_return = (self.entry_price - exit_price) / self.entry_price
            
            margin = self.equity * self.position_size
            pnl = margin * price_return * self.leverage
            equity_before = self.equity
            self.equity = equity_before + pnl
            
            self.trades[-1].update({
                "exit_time": len(self.prev_closes),
                "exit_price": exit_price,
                "exit_equity": self.equity,
                "pnl": pnl,
                "pnl_pct": (self.equity - self.trades[-1]["entry_equity"]) / self.trades[-1]["entry_equity"] * 100,
                "price_return_pct": price_return * 100,
            })
            
            if abs(self.trades[-1]["pnl_pct"]) > 10:
                print("⚠️ suspicious trade", self.trades[-1])
        
        return self.get_results()
    
    def get_results(self):
        total_trades = len(self.trades)
        if total_trades == 0:
            return {
                "strategy": self.strategy_id,
                "sharpe": 0,
                "total_trades": 0,
                "total_return": 0,
                "max_drawdown": self.max_drawdown,
                "win_rate": 0,
                "profit_factor": 0,
                "signals": self.signal_count,
                "buy_signals": self.buy_signals,
                "sell_signals": self.sell_signals,
                "equity": self.equity,
                "liquidation_count": self.liquidation_count,
                "cvd_zscore_avg": np.mean(self.cvd_zscore_values) if self.cvd_zscore_values else 0,
                "cvd_zscore_max": np.max(np.abs(self.cvd_zscore_values)) if self.cvd_zscore_values else 0,
            }
        
        winning = [t for t in self.trades if t.get("pnl") is not None and t["pnl"] > 0]
        losing = [t for t in self.trades if t.get("pnl") is not None and t["pnl"] <= 0]
        
        total_return = (self.equity - self.initial_capital) / self.initial_capital * 100
        win_rate = len(winning) / total_trades if total_trades > 0 else 0
        
        gross_profit = sum(t["pnl"] for t in winning) if winning else 0
        gross_loss = abs(sum(t["pnl"] for t in losing)) if losing else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        returns = [t.get("pnl") for t in self.trades if t.get("pnl") is not None]
        if len(returns) > 1:
            mean_ret = np.mean(returns)
            std_ret = np.std(returns)
            sharpe = mean_ret / std_ret * np.sqrt(len(returns)) if std_ret > 0 else 0
        else:
            sharpe = 0
        
        return {
            "strategy": self.strategy_id,
            "sharpe": sharpe,
            "total_trades": total_trades,
            "total_return": total_return,
            "max_drawdown": self.max_drawdown,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "signals": self.signal_count,
            "buy_signals": self.buy_signals,
            "sell_signals": self.sell_signals,
            "equity": self.equity,
            "liquidation_count": self.liquidation_count,
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "cvd_zscore_avg": np.mean(self.cvd_zscore_values) if self.cvd_zscore_values else 0,
            "cvd_zscore_max": np.max(np.abs(self.cvd_zscore_values)) if self.cvd_zscore_values else 0,
        }


def main():
    print("\n" + "=" * 80)
    print("TRADE PRESSURE STRATEGY DIAGNOSIS (FIXED EQUITY)")
    print("=" * 80 + "\n")
    
    strategies = [
        "trade_pressure_bounce",
        "trade_pressure_squeeze",
        "trade_pressure_absorption",
        "trade_pressure_exhaustion",
        "cvd_divergence_enhanced",
    ]
    
    print("Loading data...")
    bars = load_data(2023, 30000)
    print()
    
    results = []
    
    for strategy_id in strategies:
        print(f"Testing {strategy_id}...")
        
        try:
            info = get_strategy_info(strategy_id)
            params = info.default_params if info else {}
            print(f"  Params: {params}")
        except Exception as e:
            print(f"  ❌ Failed to get strategy info: {e}")
            continue
        
        try:
            tester = RealStrategyBacktester(strategy_id, params)
            result = tester.run(bars)
            results.append(result)
            
            print(f"  Signals: {result['signals']} (BUY: {result.get('buy_signals', 0)}, SELL: {result.get('sell_signals', 0)}")
            print(f"  Trades: {result['total_trades']}")
            print(f"  Liquidations: {result.get('liquidation_count', 0)}")
            print(f"  Return: {result['total_return']:.2f}%")
            print(f"  Sharpe: {result['sharpe']:.4f}")
            print(f"  Win Rate: {result['win_rate'] * 100:.1f}%")
            print(f"  PF: {result['profit_factor']:.2f}")
            print(f"  DD: {result['max_drawdown'] * 100:.2f}%")
            print(f"  Final Equity: ${result['equity']:.2f}")
            print(f"  CVD Z-Score avg: {result.get('cvd_zscore_avg', 0):.4f}, max: {result.get('cvd_zscore_max', 0):.4f}")
            print()
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            print()
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    results.sort(key=lambda x: x["total_trades"], reverse=True)
    
    print(f"\n{'Strategy':<30} {'Signals':>8} {'Trades':>8} {'Return':>12} {'Sharpe':>8} {'WinRate':>10} {'Liquid':>8}")
    print("-" * 100)
    
    for r in results:
        status = "✅" if r["total_trades"] > 10 else "⚠️" if r["total_trades"] > 0 else "❌"
        print(f"{r['strategy']:<30} {r['signals']:>8} {r['total_trades']:>8} "
              f"{r['total_return']:>12.2f}% {r['sharpe']:>8.2f} {r['win_rate'] * 100:>9.1f}% "
              f"{r.get('liquidation_count', 0):>8} {status}")


if __name__ == "__main__":
    main()
