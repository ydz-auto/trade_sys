#!/usr/bin/env python3
"""
诊断脚本：深入诊断回测异常收益
"""
import sys
import os
from pathlib import Path

script_dir = os.path.dirname(os.path.abspath(__file__))
backend_path = os.path.abspath(os.path.join(script_dir, '..', 'backend'))
sys.path.insert(0, backend_path)

from infrastructure.storage.parquet_reader import read_parquet_safe
from engines.compute.strategy.registry import get_strategy, get_strategy_info
from runtimes.replay_runtime.backtest_engine import Bar
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


class DiagnosticBacktester:
    def __init__(self, strategy_id, params=None):
        self.strategy_id = strategy_id
        self.strategy = get_strategy(strategy_id, params or {})
        
        self.prev_closes = []
        self.prev_volumes = []
        self.prev_cvds = []
        
        self.equity = 10000.0
        self.initial_capital = 10000.0
        self.position_size = 0.1  # 10% 仓位（不是杠杆，是比例）
        self.leverage = 1.0       # 1x 杠杆
        self.commission = 0.0004
        self.slippage = 0.0005
        
        self.in_position = False
        self.position_type = None  # "long" or "short"
        self.entry_price = 0
        self.trades = []
        self.equity_curve = [self.equity]
        
        self.cvd_zscore_values = []
    
    def calculate_zscore(self, values, period=240):
        if len(values) < period:
            return 0.0
        recent = np.array(values[-period:])
        mean = np.mean(recent)
        std = np.std(recent)
        return (values[-1] - mean) / std if std > 0 else 0.0
    
    def calculate_cvd_from_history(self):
        if len(self.prev_closes) < 2:
            return 0.0
        price_diff = np.diff(self.prev_closes)
        vol_array = np.array(self.prev_volumes[1:])
        cvd = np.sum(np.where(price_diff > 0, vol_array, -vol_array))
        return float(cvd)
    
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
            features["cvd_zscore"] = self.calculate_zscore(self.prev_cvds)
            self.cvd_zscore_values.append(features["cvd_zscore"])
        
        if len(self.prev_closes) > 10:
            price_moves = np.diff(self.prev_closes[-10:])
            up_vol = np.sum(np.where(price_moves > 0, self.prev_volumes[-9:], 0))
            down_vol = np.sum(np.where(price_moves < 0, self.prev_volumes[-9:], 0))
            total = up_vol + down_vol
            features["taker_buy_ratio"] = up_vol / total if total > 0 else 0.5
        
        if len(self.prev_closes) > 24:
            features["return_1h"] = (self.prev_closes[-1] - self.prev_closes[-24]) / self.prev_closes[-24]
        
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
            entry_time = bar.timestamp if 'bar' in dir() else 0
            self.trades.append({
                "type": "long",
                "entry_time": len(self.prev_closes),
                "entry_price": self.entry_price,
                "exit_time": None,
                "exit_price": None,
                "entry_equity": self.equity,
                "exit_equity": None,
                "pnl": None,
                "pnl_pct": None,
                "return_pct": None,
            })
            
        elif signal_type == "sell" and self.in_position:
            exit_price = self.prev_closes[-1] * (1 - self.slippage)
            exit_time = len(self.prev_closes)
            
            # 计算收益
            if self.position_type == "long":
                price_return = (exit_price - self.entry_price) / self.entry_price
            else:
                price_return = (self.entry_price - exit_price) / self.entry_price
            
            # position_size 是资金比例，leverage 是倍数
            # margin = equity * position_size
            # pnl = margin * price_return * leverage
            margin = self.equity * self.position_size
            pnl = margin * price_return * self.leverage
            
            # 更新 equity
            self.equity += pnl
            
            self.trades[-1].update({
                "exit_time": exit_time,
                "exit_price": exit_price,
                "exit_equity": self.equity,
                "pnl": pnl,
                "pnl_pct": (self.equity - self.trades[-1]["entry_equity"]) / self.trades[-1]["entry_equity"] * 100,
                "return_pct": price_return * 100,
                "leverage": self.leverage,
                "margin": margin,
                "notional": margin * self.leverage,
            })
            
            self.in_position = False
            self.position_type = None
            self.equity_curve.append(self.equity)
    
    def run(self, bars):
        global bar
        for bar in bars:
            self.update_history(bar)
            features = self.build_features(bar)
            
            try:
                signal_dict = self.strategy.generate_signal(features)
                if signal_dict:
                    self.execute_signal(signal_dict.get("signal_type", "hold"))
            except:
                pass
        
        if self.in_position and self.prev_closes:
            exit_price = self.prev_closes[-1] * (1 - self.slippage)
            price_return = (exit_price - self.entry_price) / self.entry_price
            margin = self.equity * self.position_size
            pnl = margin * price_return * self.leverage
            self.equity += pnl
            self.trades[-1].update({
                "exit_time": len(self.prev_closes),
                "exit_price": exit_price,
                "exit_equity": self.equity,
                "pnl": pnl,
                "pnl_pct": (self.equity - self.trades[-1]["entry_equity"]) / self.trades[-1]["entry_equity"] * 100,
                "return_pct": price_return * 100,
            })
        
        return self.get_results()
    
    def get_results(self):
        total_return = (self.equity - self.initial_capital) / self.initial_capital * 100
        self.final_equity = self.equity
        return {
            "trades": self.trades,
            "equity_curve": self.equity_curve,
            "final_equity": self.equity,
            "total_return": total_return,
        }
    
    def print_trade_analysis(self):
        print("\n" + "="*100)
        print(f"DETAILED TRADE ANALYSIS: {self.strategy_id}")
        print("="*100)
        
        if not self.trades:
            print("No trades!")
            return
        
        print(f"\nTotal trades: {len(self.trades)}")
        print(f"Initial capital: ${self.initial_capital:.2f}")
        print(f"Final equity: ${self.final_equity:.2f}")
        print(f"Total return: {(self.final_equity - self.initial_capital) / self.initial_capital * 100:.2f}%")
        print()
        
        # 打印前 5 笔和后 5 笔交易
        trades_to_show = []
        if len(self.trades) > 10:
            trades_to_show = self.trades[:5] + [{"...": "..."}] + self.trades[-5:]
        else:
            trades_to_show = self.trades
        
        print(f"{'#':<4} {'Type':<6} {'Entry Price':>12} {'Exit Price':>12} {'Return%':>10} {'PnL $':>12} {'Equity After':>14} {'Margin':>12} {'Leverage':>9}")
        print("-" * 100)
        
        for i, trade in enumerate(trades_to_show):
            if isinstance(trade, dict) and "..." in trade:
                print("  ...")
                continue
            print(f"{i:<4} {trade['type']:<6} {trade['entry_price']:>12.2f} {trade['exit_price']:>12.2f} "
                  f"{trade.get('return_pct', 0):>10.2f}% {trade.get('pnl', 0):>12.2f} "
                  f"{trade.get('exit_equity', 0):>14.2f} {trade.get('margin', 0):>12.2f} {trade.get('leverage', 1):>9.1f}x")
        
        # 分析异常
        print("\n" + "="*100)
        print("ANOMALY DETECTION")
        print("="*100)
        
        anomalous_trades = []
        for i, trade in enumerate(self.trades):
            pnl_pct = trade.get("pnl_pct", 0)
            equity_ratio = trade.get("exit_equity", 0) / trade.get("entry_equity", 1) if trade.get("entry_equity", 0) > 0 else 0
            
            if abs(pnl_pct) > 1000:
                anomalous_trades.append((i, "pnl_pct > 1000%", trade))
            elif equity_ratio > 10:
                anomalous_trades.append((i, f"equity_ratio > 10x ({equity_ratio:.1f}x)", trade))
            elif trade.get("entry_price", 0) <= 0 or trade.get("exit_price", 0) <= 0:
                anomalous_trades.append((i, "price <= 0", trade))
        
        if anomalous_trades:
            print("\n⚠️  ANOMALOUS TRADES FOUND:")
            for i, reason, trade in anomalous_trades:
                print(f"\n  Trade #{i}: {reason}")
                print(f"    entry_price: {trade.get('entry_price')}")
                print(f"    exit_price: {trade.get('exit_price')}")
                print(f"    pnl_pct: {trade.get('pnl_pct')}%")
                print(f"    return_pct: {trade.get('return_pct')}%")
                print(f"    entry_equity: {trade.get('entry_equity')}")
                print(f"    exit_equity: {trade.get('exit_equity')}")
                print(f"    margin: {trade.get('margin')}")
                print(f"    leverage: {trade.get('leverage')}")
                print(f"    notional: {trade.get('notional')}")
                print(f"    pnl: {trade.get('pnl')}")
        else:
            print("\n✅ No anomalous trades detected")
        
        # PnL 分布统计
        pnls = [t.get("pnl", 0) for t in self.trades if t.get("pnl") is not None]
        returns = [t.get("return_pct", 0) for t in self.trades if t.get("return_pct") is not None]
        
        if pnls:
            print(f"\nPnL Statistics:")
            print(f"  Min: ${min(pnls):.2f}")
            print(f"  Max: ${max(pnls):.2f}")
            print(f"  Mean: ${np.mean(pnls):.2f}")
            print(f"  Total: ${sum(pnls):.2f}")
        
        if returns:
            print(f"\nReturn Statistics:")
            print(f"  Min: {min(returns):.2f}%")
            print(f"  Max: {max(returns):.2f}%")
            print(f"  Mean: {np.mean(returns):.2f}%")


def main():
    strategies = [
        "cvd_divergence_enhanced",
        "trade_pressure_absorption",
    ]
    
    print("Loading data...")
    bars = load_data(2023, 30000)
    print()
    
    for strategy_id in strategies:
        print(f"\n{'='*80}")
        print(f"TESTING: {strategy_id}")
        print(f"{'='*80}")
        
        try:
            info = get_strategy_info(strategy_id)
            params = info.default_params if info else {}
            print(f"Params: {params}")
        except:
            params = {}
        
        tester = DiagnosticBacktester(strategy_id, params)
        result = tester.run(bars)
        tester.print_trade_analysis()


if __name__ == "__main__":
    main()
