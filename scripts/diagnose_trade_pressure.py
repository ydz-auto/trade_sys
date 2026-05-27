#!/usr/bin/env python3
"""
诊断脚本：测试 Trade Pressure Framework 策略
修复：消除未来函数，使用更真实的回测逻辑
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
from datetime import datetime


def load_data(year=2023, max_bars=50000):
    """加载数据"""
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
    """使用真实策略的回测器 - 修复未来函数"""
    
    def __init__(self, strategy_id, params=None):
        self.strategy_id = strategy_id
        self.strategy = get_strategy(strategy_id, params or {})
        
        # 历史数据（上一根 bar 的数据）
        self.prev_closes = []
        self.prev_volumes = []
        self.prev_cvds = []
        
        # Backtest state
        self.equity = 10000.0
        self.position_size = 0.1  # 10% 仓位
        self.commission = 0.0004  # 0.04%
        self.slippage = 0.0005    # 0.05%
        self.max_equity = self.equity
        self.max_drawdown = 0.0
        self.in_position = False
        self.entry_price = 0
        self.trades = []
        
        # Signal tracking
        self.signal_count = 0
        self.buy_signals = 0
        self.sell_signals = 0
        self.liquidation_count = 0
        
        # Diagnostics
        self.cvd_zscore_values = []
        self.volume_zscore_values = []
    
    def calculate_rsi(self, period=14):
        if len(self.prev_closes) < period + 1:
            return 50.0
        deltas = np.diff(self.prev_closes)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        if avg_loss == 0:
            return 100.0
        return 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))
    
    def calculate_ema(self, period):
        if len(self.prev_closes) < period:
            return self.prev_closes[-1] if self.prev_closes else 0
        weights = np.exp(np.linspace(-1., 0., period))
        weights /= weights.sum()
        return float(np.convolve(self.prev_closes, weights, mode='valid')[-1])
    
    def calculate_bollinger_bands(self, period=20):
        if len(self.prev_closes) < period:
            return None, None, None
        recent = self.prev_closes[-period:]
        sma = np.mean(recent)
        std = np.std(recent)
        return sma + 2 * std, sma, sma - 2 * std
    
    def calculate_volume_ratio(self, period=24):
        if len(self.prev_volumes) < period + 1:
            return 1.0
        current = self.prev_volumes[-1]
        avg = np.mean(self.prev_volumes[-period-1:-1])
        return current / avg if avg > 0 else 1.0
    
    def calculate_cvd_from_history(self):
        """从历史数据计算 CVD（不包含当前 bar）"""
        if len(self.prev_closes) < 2:
            return 0.0
        price_diff = np.diff(self.prev_closes)
        vol_array = np.array(self.prev_volumes[1:])
        cvd = np.sum(np.where(price_diff > 0, vol_array, -vol_array))
        return float(cvd)
    
    def calculate_zscore(self, values, period=240):
        """计算 Z-Score，只使用历史数据"""
        if len(values) < period:
            return 0.0
        recent = np.array(values[-period:])
        mean = np.mean(recent)
        std = np.std(recent)
        return (values[-1] - mean) / std if std > 0 else 0.0
    
    def build_features(self, bar):
        """构建特征 - 使用上一根 bar 的数据，避免未来函数"""
        # 使用上一根 bar 的数据（bar.close 是当前 bar 的收盘价，但 cvd 是用历史数据算的）
        features = {
            "close": bar.close,
            "high": bar.high,
            "low": bar.low,
            "volume": bar.volume,
            "close_prices": self.prev_closes + [bar.close],  # 包含当前 close
            "high_prices": self.prev_closes,  # 用 close 代替
            "low_prices": self.prev_closes,
            "volumes": self.prev_volumes + [bar.volume],
            "symbol": "BTCUSDT",
            "timestamp": bar.timestamp
        }
        
        # Technical indicators（使用历史数据）
        if len(self.prev_closes) > 14:
            features["rsi_14"] = self.calculate_rsi(14)
        
        if len(self.prev_closes) > 50:
            features["ema_fast"] = self.calculate_ema(10)
            features["ema_slow"] = self.calculate_ema(50)
        
        bb_upper, bb_middle, bb_lower = self.calculate_bollinger_bands()
        if bb_upper:
            features["bb_upper"] = bb_upper
            features["bb_middle"] = bb_middle
            features["bb_lower"] = bb_lower
        
        features["volume_ratio"] = self.calculate_volume_ratio()
        
        # CVD 相关特征 - 使用历史 CVD
        if len(self.prev_cvds) > 10:
            features["cvd"] = self.prev_cvds[-1]
            features["cvd_zscore"] = self.calculate_zscore(self.prev_cvds)
            self.cvd_zscore_values.append(features["cvd_zscore"])
        
        # Return features - 使用历史数据
        if len(self.prev_closes) > 24:
            features["return_1h"] = (self.prev_closes[-1] - self.prev_closes[-24]) / self.prev_closes[-24]
        
        # Buy/sell imbalance
        if len(self.prev_closes) > 10:
            price_moves = np.diff(self.prev_closes[-10:])
            up_vol = np.sum(np.where(price_moves > 0, self.prev_volumes[-9:], 0))
            down_vol = np.sum(np.where(price_moves < 0, self.prev_volumes[-9:], 0))
            total = up_vol + down_vol
            features["taker_buy_ratio"] = up_vol / total if total > 0 else 0.5
        
        return features
    
    def update_history(self, bar):
        """在 bar 处理完后更新历史数据"""
        self.prev_closes.append(bar.close)
        self.prev_volumes.append(bar.volume)
        
        if len(self.prev_closes) > 600:
            self.prev_closes = self.prev_closes[-600:]
            self.prev_volumes = self.prev_volumes[-600:]
        
        # 计算 CVD 并添加到历史
        cvd = self.calculate_cvd_from_history()
        self.prev_cvds.append(cvd)
        if len(self.prev_cvds) > 1000:
            self.prev_cvds = self.prev_cvds[-1000:]
    
    def execute_signal(self, signal_type):
        """执行交易信号"""
        if signal_type == "buy" and not self.in_position:
            self.entry_price = self.prev_closes[-1] * (1 + self.slippage) if self.prev_closes else 0
            cost = self.equity * self.position_size * (self.commission + self.slippage)
            self.equity -= cost
            self.in_position = True
            self.trades.append({"type": "long", "entry": self.entry_price, "pnl": 0, "exit": None})
            self.buy_signals += 1
            
        elif signal_type == "sell" and self.in_position:
            exit_price = self.prev_closes[-1] * (1 - self.slippage) if self.prev_closes else 0
            pnl_pct = (exit_price - self.entry_price) / self.entry_price if self.entry_price > 0 else 0
            pnl = self.equity * self.position_size * pnl_pct
            cost = self.equity * self.position_size * self.commission
            self.equity += pnl - cost
            self.trades[-1]["exit"] = exit_price
            self.trades[-1]["pnl"] = pnl
            self.in_position = False
            self.sell_signals += 1
    
    def check_liquidation(self):
        """检查爆仓 - 仓位亏损超过 80% 时强平"""
        if not self.in_position:
            return
        
        if len(self.prev_closes) < 1:
            return
        
        current_price = self.prev_closes[-1]
        pnl_pct = (current_price - self.entry_price) / self.entry_price if self.entry_price > 0 else 0
        position_loss = pnl_pct * self.position_size
        
        # 如果亏损超过保证金的 80%，爆仓
        if position_loss < -0.80:
            self.equity *= (1 + position_loss)  # 剩余 20%
            self.liquidation_count += 1
            self.in_position = False
            if self.trades:
                self.trades[-1]["exit"] = current_price
                self.trades[-1]["pnl"] = self.equity * self.position_size * pnl_pct
                self.trades[-1]["liquidation"] = True
    
    def update_equity(self):
        """更新权益"""
        if self.in_position and len(self.prev_closes) > 0:
            pnl_pct = (self.prev_closes[-1] - self.entry_price) / self.entry_price if self.entry_price > 0 else 0
            self.equity += self.equity * self.position_size * pnl_pct
            
            # 检查爆仓
            self.check_liquidation()
        
        self.max_equity = max(self.max_equity, self.equity)
        dd = (self.max_equity - self.equity) / self.max_equity if self.max_equity > 0 else 0
        self.max_drawdown = max(self.max_drawdown, dd)
    
    def run(self, bars):
        """运行回测"""
        for bar in bars:
            # 先更新历史数据
            self.update_history(bar)
            
            # 构建特征（使用历史数据，避免未来函数）
            features = self.build_features(bar)
            
            # 生成信号
            try:
                signal_dict = self.strategy.generate_signal(features)
                if signal_dict:
                    self.signal_count += 1
                    self.execute_signal(signal_dict.get("signal_type", "hold"))
            except Exception as e:
                pass
            
            # 更新权益
            self.update_equity()
        
        # Close open position at end
        if self.in_position and self.prev_closes:
            exit_price = self.prev_closes[-1] * (1 - self.slippage)
            pnl_pct = (exit_price - self.entry_price) / self.entry_price if self.entry_price > 0 else 0
            self.equity += self.equity * self.position_size * pnl_pct
            self.trades[-1]["exit"] = exit_price
            self.trades[-1]["pnl"] = self.equity * self.position_size * pnl_pct
        
        return self.get_results()
    
    def get_results(self):
        """获取结果"""
        total_trades = len(self.trades)
        if total_trades == 0:
            return {
                "strategy": self.strategy_id,
                "sharpe": 0,
                "total_trades": 0,
                "total_return": 0,
                "max_drawdown": 0,
                "win_rate": 0,
                "profit_factor": 0,
                "signals": self.signal_count,
                "equity": self.equity,
                "liquidation_count": self.liquidation_count,
                "cvd_zscore_avg": np.mean(self.cvd_zscore_values) if self.cvd_zscore_values else 0,
            }
        
        winning = [t for t in self.trades if t["pnl"] > 0]
        losing = [t for t in self.trades if t["pnl"] <= 0]
        
        total_return = (self.equity - 10000) / 10000
        win_rate = len(winning) / total_trades
        gross_profit = sum(t["pnl"] for t in winning)
        gross_loss = abs(sum(t["pnl"] for t in losing))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Simple Sharpe approximation
        returns = [t["pnl"] for t in self.trades if t["pnl"] != 0]
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
    print("\n" + "="*80)
    print("TRADE PRESSURE STRATEGY DIAGNOSIS (FIXED)")
    print("="*80 + "\n")
    
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
            print(f"  Default params: {params}")
        except Exception as e:
            print(f"  ❌ Failed to get strategy info: {e}")
            continue
        
        try:
            tester = RealStrategyBacktester(strategy_id, params)
            result = tester.run(bars)
            results.append(result)
            
            print(f"  Signals: {result['signals']} (BUY: {result.get('buy_signals', 0)}, SELL: {result.get('sell_signals', 0)})")
            print(f"  Trades: {result['total_trades']}")
            print(f"  Liquidations: {result.get('liquidation_count', 0)}")
            print(f"  Return: {result['total_return']*100:.2f}%")
            print(f"  Sharpe: {result['sharpe']:.4f}")
            print(f"  Win Rate: {result['win_rate']*100:.1f}%")
            print(f"  PF: {result['profit_factor']:.2f}")
            print(f"  DD: {result['max_drawdown']*100:.2f}%")
            print(f"  Final Equity: ${result['equity']:.2f}")
            print(f"  CVD Z-Score avg: {result.get('cvd_zscore_avg', 0):.4f}, max: {result.get('cvd_zscore_max', 0):.4f}")
            print()
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            print()
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    results.sort(key=lambda x: x["total_trades"], reverse=True)
    
    print(f"\n{'Strategy':<30} {'Signals':>8} {'Trades':>8} {'Return':>10} {'Sharpe':>8} {'WinRate':>8} {'Liquid':>8}")
    print("-" * 90)
    
    for r in results:
        status = "✅" if r["total_trades"] > 10 else "⚠️" if r["total_trades"] > 0 else "❌"
        print(f"{r['strategy']:<30} {r['signals']:>8} {r['total_trades']:>8} "
              f"{r['total_return']*100:>9.1f}% {r['sharpe']:>8.2f} {r['win_rate']*100:>7.1f}% "
              f"{r.get('liquidation_count', 0):>8} {status}")


if __name__ == "__main__":
    main()
