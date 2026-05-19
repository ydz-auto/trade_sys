#!/usr/bin/env python3
"""
BTC 做空策略深度回测 - 按本金百分比止损版本

关键改进：
- 止损按本金百分比计算（如10%本金止损）
- 自动根据杠杆调整价格止损位
- 更合理的风控设置
"""

import sys
from pathlib import Path

script_dir = Path(__file__).parent
backend_path = script_dir.parent
sys.path.insert(0, str(backend_path))

import json
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, List, Optional
import pandas as pd
import numpy as np

from infrastructure.logging import get_logger

logger = get_logger("short_strategy_backtest_capital_sl")


OPTIMIZED_STRATEGIES = {
    "volume_climax_fade_v2": {
        "name": "Volume Climax Fade V2",
        "direction": -1,
        "detection_description": "放量高潮后回落（优化版）",
        "conditions": {
            "volume_ratio_min": 2.0,
            "wick_ratio_min": 0.3,
            "returns_min": 0.003,
        },
        "capital_stop_loss": 0.10,  # 本金止损 10%
        "capital_take_profit": 0.15,  # 本金止盈 15%
        "min_holds": 12,
    },
    "weak_bounce_short_v2": {
        "name": "Weak Bounce Short V2",
        "direction": -1,
        "detection_description": "弱反弹做空（优化版）",
        "conditions": {
            "drop_threshold_4h": 0.02,
            "bounce_min": 0.003,
            "bounce_max": 0.015,
            "volume_ratio_min": 1.5,
        },
        "capital_stop_loss": 0.10,  # 本金止损 10%
        "capital_take_profit": 0.20,  # 本金止盈 20%
        "min_holds": 24,
    },
    "fake_breakout_trap_v2": {
        "name": "Fake Breakout Trap V2",
        "direction": -1,
        "detection_description": "假突破反杀（优化版）",
        "conditions": {
            "breakout_ratio": 1.005,
            "volume_ratio_max": 1.2,
            "price_rejection": True,
        },
        "capital_stop_loss": 0.08,  # 本金止损 8%
        "capital_take_profit": 0.12,  # 本金止盈 12%
        "min_holds": 12,
    },
    "weekend_liquidity_trap_v2": {
        "name": "Weekend Liquidity Trap V2",
        "direction": 0,
        "detection_description": "周末低流动性陷阱（优化版）",
        "conditions": {
            "volume_ratio_max": 0.5,
            "spike_min": 0.003,
            "asian_hours": [0, 1, 2, 3, 4, 5, 6, 7],
        },
        "capital_stop_loss": 0.05,  # 本金止损 5%
        "capital_take_profit": 0.08,  # 本金止盈 8%
        "min_holds": 6,
    },
    "short_squeeze_hunt_v2": {
        "name": "Short Squeeze Hunt V2",
        "direction": 1,
        "detection_description": "抓空头挤压（优化版）",
        "conditions": {
            "funding_rate_max": -0.00005,
            "oi_change_min": 0.01,
            "price_spike_min": 0.008,
        },
        "capital_stop_loss": 0.10,  # 本金止损 10%
        "capital_take_profit": 0.15,  # 本金止盈 15%
        "min_holds": 24,
    },
    "funding_reset_v2": {
        "name": "Funding Reset V2",
        "direction": -1,
        "detection_description": "资金费率重置（优化版）",
        "conditions": {
            "funding_rate_min": 0.0003,
            "funding_delta_max": -0.00005,
        },
        "capital_stop_loss": 0.10,  # 本金止损 10%
        "capital_take_profit": 0.12,  # 本金止盈 12%
        "min_holds": 24,
    },
}


class ShortStrategyBacktesterCapitalSL:
    def __init__(self, initial_capital: float = 10000, leverage: float = 50):
        self.initial_capital = initial_capital
        self.leverage = leverage
        self.results = {}
        self.trade_log = []
    
    def load_data(self, months: int = 5) -> pd.DataFrame:
        data_path = backend_path / "data_lake/features/binance/BTCUSDT/features_with_structure.parquet"
        
        try:
            df = pd.read_parquet(data_path)
        except Exception as e:
            logger.warning(f"Cannot load parquet file: {e}")
            return pd.DataFrame()
        
        cutoff = datetime.now() - timedelta(days=months * 30)
        df = df[df["timestamp"] >= pd.Timestamp(cutoff)].copy()
        
        df = df.sort_values("timestamp").reset_index(drop=True)
        
        logger.info(f"Loaded {len(df)} rows, date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        
        return df
    
    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        df["hour"] = df["timestamp"].dt.hour
        df["day_of_week"] = df["timestamp"].dt.dayofweek
        df["is_weekend"] = df["day_of_week"] >= 5
        
        if "volume" in df.columns:
            df["volume_ratio"] = df["volume"] / df["volume"].rolling(288).mean()
        
        if "high" in df.columns and "close" in df.columns and "low" in df.columns:
            df["wick_ratio"] = (df["high"] - df["close"]) / (df["high"] - df["low"] + 0.001)
            df["body_ratio"] = abs(df["close"] - df["open"]) / (df["high"] - df["low"] + 0.001)
        
        df["returns_5m"] = df["close"].pct_change(1)
        df["returns_15m"] = df["close"].pct_change(3)
        df["returns_1h"] = df["close"].pct_change(12)
        df["returns_4h"] = df["close"].pct_change(48)
        
        if "funding_rate" in df.columns:
            df["funding_delta"] = df["funding_rate"].diff(12)
        
        if "open_interest" in df.columns:
            df["oi_change_1h"] = df["open_interest"].pct_change(12)
        
        return df
    
    def detect_volume_climax_fade_v2(self, row: pd.Series, config: Dict) -> bool:
        c = config["conditions"]
        volume_ok = row.get("volume_ratio", 0) >= c["volume_ratio_min"]
        wick_ok = row.get("wick_ratio", 0) >= c["wick_ratio_min"]
        returns_ok = abs(row.get("returns_5m", 0)) >= c["returns_min"]
        price_up = row.get("returns_5m", 0) > 0
        return volume_ok and wick_ok and returns_ok and price_up
    
    def detect_weak_bounce_short_v2(self, row: pd.Series, prev_rows: pd.DataFrame, config: Dict) -> bool:
        if len(prev_rows) < 60:
            return False
        c = config["conditions"]
        close_4h_ago = prev_rows["close"].iloc[-48]
        close_1h_ago = prev_rows["close"].iloc[-12]
        current_close = row["close"]
        drop_4h_pct = (close_4h_ago - close_1h_ago) / close_4h_ago
        bounce_pct = (current_close - close_1h_ago) / close_1h_ago
        drop_ok = drop_4h_pct >= c["drop_threshold_4h"]
        bounce_ok = c["bounce_min"] <= bounce_pct <= c["bounce_max"]
        volume_ok = row.get("volume_ratio", 0) >= c["volume_ratio_min"]
        return drop_ok and bounce_ok and volume_ok
    
    def detect_fake_breakout_trap_v2(self, row: pd.Series, prev_rows: pd.DataFrame, config: Dict) -> bool:
        if len(prev_rows) < 24:
            return False
        c = config["conditions"]
        rolling_high = prev_rows["high"].iloc[-24:].max()
        breakout = row.get("high", 0) > rolling_high * c["breakout_ratio"]
        volume_ok = row.get("volume_ratio", 1) <= c["volume_ratio_max"]
        price_rejected = row.get("close", 0) < row.get("high", 0) * 0.998
        return breakout and volume_ok and price_rejected
    
    def detect_weekend_liquidity_trap_v2(self, row: pd.Series, config: Dict) -> bool:
        c = config["conditions"]
        is_weekend_or_early = row.get("is_weekend", False) or row.get("hour", 0) in c["asian_hours"]
        low_volume = row.get("volume_ratio", 1) <= c["volume_ratio_max"]
        price_spike = abs(row.get("returns_5m", 0)) >= c["spike_min"]
        return is_weekend_or_early and low_volume and price_spike
    
    def detect_short_squeeze_hunt_v2(self, row: pd.Series, config: Dict) -> bool:
        c = config["conditions"]
        funding_ok = row.get("funding_rate", 0) <= c["funding_rate_max"]
        oi_ok = row.get("oi_change_1h", 0) >= c["oi_change_min"]
        price_ok = row.get("returns_1h", 0) >= c["price_spike_min"]
        return funding_ok and oi_ok and price_ok
    
    def detect_funding_reset_v2(self, row: pd.Series, config: Dict) -> bool:
        c = config["conditions"]
        funding_high = row.get("funding_rate", 0) >= c["funding_rate_min"]
        funding_dropping = row.get("funding_delta", 0) <= c["funding_delta_max"]
        return funding_high and funding_dropping
    
    def run_strategy_with_capital_sl(
        self, 
        strategy_key: str, 
        df: pd.DataFrame, 
        detector_func,
        config: Dict
    ) -> List[Dict]:
        """运行单个策略，按本金百分比止损"""
        trades = []
        
        capital_stop_loss_pct = config["capital_stop_loss"]
        capital_take_profit_pct = config["capital_take_profit"]
        
        price_stop_loss_pct = capital_stop_loss_pct / self.leverage
        price_take_profit_pct = capital_take_profit_pct / self.leverage
        
        for i in range(100, len(df)):
            row = df.iloc[i]
            prev_rows = df.iloc[max(0, i-300):i]
            
            try:
                if "prev_rows" in detector_func.__code__.co_varnames:
                    triggered = detector_func(row, prev_rows, config)
                else:
                    triggered = detector_func(row, config)
            except Exception as e:
                continue
            
            if triggered:
                entry_price = row["close"]
                entry_time = row["timestamp"]
                entry_idx = i
                direction = config["direction"]
                
                if direction == -1:  # 做空
                    stop_loss_price = entry_price * (1 + price_stop_loss_pct)
                    take_profit_price = entry_price * (1 - price_take_profit_pct)
                else:  # 做多
                    stop_loss_price = entry_price * (1 - price_stop_loss_pct)
                    take_profit_price = entry_price * (1 + price_take_profit_pct)
                
                exit_idx = min(entry_idx + config["min_holds"], len(df) - 1)
                exit_price = None
                exit_time = None
                exit_reason = "time_exit"
                
                for j in range(entry_idx + 1, exit_idx + 1):
                    bar = df.iloc[j]
                    
                    if direction == -1:  # 做空
                        if bar["high"] >= stop_loss_price:
                            exit_price = stop_loss_price
                            exit_time = bar["timestamp"]
                            exit_reason = "stop_loss"
                            break
                        elif bar["low"] <= take_profit_price:
                            exit_price = take_profit_price
                            exit_time = bar["timestamp"]
                            exit_reason = "take_profit"
                            break
                    else:  # 做多
                        if bar["low"] <= stop_loss_price:
                            exit_price = stop_loss_price
                            exit_time = bar["timestamp"]
                            exit_reason = "stop_loss"
                            break
                        elif bar["high"] >= take_profit_price:
                            exit_price = take_profit_price
                            exit_time = bar["timestamp"]
                            exit_reason = "take_profit"
                            break
                
                if exit_price is None:
                    exit_price = df.iloc[exit_idx]["close"]
                    exit_time = df.iloc[exit_idx]["timestamp"]
                
                ret_raw = ((exit_price - entry_price) / entry_price) * direction
                ret_leveraged = ret_raw * self.leverage
                
                capital_pnl = ret_leveraged * self.initial_capital
                
                trades.append({
                    "strategy": strategy_key,
                    "name": config["name"],
                    "direction": "做空" if direction == -1 else "做多",
                    "entry_time": entry_time,
                    "exit_time": exit_time,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "return_raw": ret_raw,
                    "return_leveraged": ret_leveraged,
                    "capital_pnl": capital_pnl,
                    "exit_reason": exit_reason,
                    "duration_bars": j - entry_idx if exit_reason != "time_exit" else config["min_holds"],
                    "price_stop_loss_pct": price_stop_loss_pct,
                    "price_take_profit_pct": price_take_profit_pct,
                })
        
        return trades
    
    def analyze_strategy(self, trades: List[Dict], config: Dict) -> Dict:
        """分析策略表现"""
        if not trades:
            return {
                "name": config["name"],
                "direction": "做空" if config["direction"] == -1 else "做多",
                "events": 0,
                "win_rate": 0,
                "avg_ret_1h": 0,
                "best_ret": 0,
                "worst_ret": 0,
                "total_pnl": 0,
                "stop_loss_count": 0,
                "take_profit_count": 0,
                "time_exit_count": 0,
                "capital_stop_loss": config["capital_stop_loss"],
                "capital_take_profit": config["capital_take_profit"],
                "price_stop_loss": config["capital_stop_loss"] / self.leverage,
                "price_take_profit": config["capital_take_profit"] / self.leverage,
            }
        
        returns = [t["return_leveraged"] for t in trades]
        wins = sum(1 for r in returns if r > 0)
        
        stop_loss_count = sum(1 for t in trades if t.get("exit_reason") == "stop_loss")
        take_profit_count = sum(1 for t in trades if t.get("exit_reason") == "take_profit")
        time_exit_count = sum(1 for t in trades if t.get("exit_reason") == "time_exit")
        
        total_pnl = sum([t["capital_pnl"] for t in trades])
        
        return {
            "name": config["name"],
            "direction": "做空" if config["direction"] == -1 else "做多",
            "events": len(trades),
            "win_rate": wins / len(trades) if trades else 0,
            "avg_ret_1h": np.mean(returns) if returns else 0,
            "best_ret": max(returns) if returns else 0,
            "worst_ret": min(returns) if returns else 0,
            "total_pnl": total_pnl,
            "stop_loss_count": stop_loss_count,
            "take_profit_count": take_profit_count,
            "time_exit_count": time_exit_count,
            "capital_stop_loss": config["capital_stop_loss"],
            "capital_take_profit": config["capital_take_profit"],
            "price_stop_loss": config["capital_stop_loss"] / self.leverage,
            "price_take_profit": config["capital_take_profit"] / self.leverage,
        }
    
    def run_all(self, df: pd.DataFrame) -> Dict:
        """运行所有优化策略"""
        logger.info("Running optimized short strategy backtest with capital-based stop loss...")
        
        all_trades = []
        
        detectors = {
            "volume_climax_fade_v2": (self.detect_volume_climax_fade_v2, OPTIMIZED_STRATEGIES["volume_climax_fade_v2"]),
            "weak_bounce_short_v2": (self.detect_weak_bounce_short_v2, OPTIMIZED_STRATEGIES["weak_bounce_short_v2"]),
            "fake_breakout_trap_v2": (self.detect_fake_breakout_trap_v2, OPTIMIZED_STRATEGIES["fake_breakout_trap_v2"]),
            "weekend_liquidity_trap_v2": (self.detect_weekend_liquidity_trap_v2, OPTIMIZED_STRATEGIES["weekend_liquidity_trap_v2"]),
            "short_squeeze_hunt_v2": (self.detect_short_squeeze_hunt_v2, OPTIMIZED_STRATEGIES["short_squeeze_hunt_v2"]),
            "funding_reset_v2": (self.detect_funding_reset_v2, OPTIMIZED_STRATEGIES["funding_reset_v2"]),
        }
        
        for strategy_key, (detector, config) in detectors.items():
            logger.info(f"Testing {config['name']}...")
            trades = self.run_strategy_with_capital_sl(strategy_key, df, detector, config)
            all_trades.extend(trades)
            
            result = self.analyze_strategy(trades, config)
            self.results[strategy_key] = result
            
            logger.info(f"  Found {len(trades)} trades, Win rate: {result['win_rate']*100:.1f}%, Avg return: {result['avg_ret_1h']*100:+.2f}%")
            logger.info(f"  Stop loss: {result['stop_loss_count']}, Take profit: {result['take_profit_count']}, Time exit: {result['time_exit_count']}")
            logger.info(f"  Capital SL: {result['capital_stop_loss']*100:.0f}%, Price SL: {result['price_stop_loss']*100:.2f}%")
        
        self.trade_log = all_trades
        
        return self.results
    
    def print_report(self):
        """打印回测报告"""
        print("\n" + "=" * 160)
        print("📊 BTC 做空/双向策略深度回测报告（按本金百分比止损）")
        print("=" * 160)
        print(f"初始资金: ${self.initial_capital:,.0f} | 杠杆: {self.leverage}x")
        print()
        
        print(f"{'策略':<30} | {'方向':<6} | {'样本':<6} | {'胜率':<8} | {'平均收益':<12} | {'最佳':<10} | {'最差':<10} | {'止损':<6} | {'止盈':<6} | {'时间退':<6} | {'本金止损':<10} | {'价格止损':<10}")
        print("-" * 160)
        
        sorted_results = sorted(
            self.results.items(),
            key=lambda x: -(x[1]["avg_ret_1h"] * x[1]["events"])
        )
        
        for key, r in sorted_results:
            if r["events"] == 0:
                continue
            
            win_rate_str = f"{r['win_rate']*100:.1f}%"
            avg_ret_str = f"{r['avg_ret_1h']*100:+.2f}%"
            best_str = f"{r['best_ret']*100:+.1f}%"
            worst_str = f"{r['worst_ret']*100:+.1f}%"
            capital_sl_str = f"{r['capital_stop_loss']*100:.0f}%"
            price_sl_str = f"{r['price_stop_loss']*100:.2f}%"
            
            print(f"{r['name']:<30} | {r['direction']:<6} | {r['events']:<6} | {win_rate_str:<8} | {avg_ret_str:>10} | {best_str:>8} | {worst_str:>8} | {r['stop_loss_count']:<6} | {r['take_profit_count']:<6} | {r['time_exit_count']:<6} | {capital_sl_str:<10} | {price_sl_str:<10}")
        
        print()
        print("=" * 160)
        print("🏆 TOP 3 做空/双向策略（按本金百分比止损）")
        print("=" * 160)
        
        for i, (key, r) in enumerate(sorted_results[:3], 1):
            if r["events"] == 0:
                continue
            
            print(f"\n  {i}. {r['name']}")
            print(f"     方向: {r['direction']} | 样本: {r['events']}笔 | 胜率: {r['win_rate']*100:.1f}%")
            print(f"     平均收益: {r['avg_ret_1h']*100:+.2f}% | 最佳: {r['best_ret']*100:+.1f}% | 最差: {r['worst_ret']*100:+.1f}%")
            print(f"     退出方式: 止损{r['stop_loss_count']}笔 | 止盈{r['take_profit_count']}笔 | 时间退{r['time_exit_count']}笔")
            print(f"     止损设置: 本金止损 {r['capital_stop_loss']*100:.0f}% = 价格止损 {r['price_stop_loss']*100:.2f}%")
            print(f"     止盈设置: 本金止盈 {r['capital_take_profit']*100:.0f}% = 价格止盈 {r['price_take_profit']*100:.2f}%")
        
        print()
        print("=" * 160)
        print("📋 策略详细分析")
        print("=" * 160)
        
        for key, r in sorted_results:
            if r["events"] == 0:
                continue
            
            config = OPTIMIZED_STRATEGIES[key]
            
            print(f"\n【{r['name']}】")
            print(f"  方向: {r['direction']} | 触发条件: {config['detection_description']}")
            print(f"  止损设置:")
            print(f"    - 本金止损: {r['capital_stop_loss']*100:.0f}%")
            print(f"    - 价格止损: {r['price_stop_loss']*100:.2f}% (本金止损 ÷ {self.leverage}x杠杆)")
            print(f"  止盈设置:")
            print(f"    - 本金止盈: {r['capital_take_profit']*100:.0f}%")
            print(f"    - 价格止盈: {r['price_take_profit']*100:.2f}% (本金止盈 ÷ {self.leverage}x杠杆)")
            
            if r["events"] > 0:
                print(f"  样本量: {r['events']} | 胜率: {r['win_rate']*100:.1f}%")
                print(f"  平均收益: {r['avg_ret_1h']*100:+.2f}% (50x杠杆)")
                print(f"  收益分布: 最佳 {r['best_ret']*100:+.1f}%, 最差 {r['worst_ret']*100:+.1f}%")
                print(f"  退出分析:")
                print(f"    - 止损触发: {r['stop_loss_count']}笔 ({r['stop_loss_count']/r['events']*100:.1f}%)")
                print(f"    - 止盈触发: {r['take_profit_count']}笔 ({r['take_profit_count']/r['events']*100:.1f}%)")
                print(f"    - 时间退出: {r['time_exit_count']}笔 ({r['time_exit_count']/r['events']*100:.1f}%)")
                
                if r['win_rate'] >= 0.6:
                    print(f"  ✅ 评估: 推荐使用")
                elif r['win_rate'] >= 0.5:
                    print(f"  ⚠️ 评估: 可考虑使用，需配合严格风控")
                else:
                    print(f"  ❌ 评估: 不推荐使用")
        
        print()
        print("=" * 160)
    
    def save_results(self):
        """保存结果"""
        output_path = backend_path / "data_lake/research/short_strategy_backtest_capital_sl_results.json"
        
        output_data = {
            "backtest_info": {
                "initial_capital": self.initial_capital,
                "leverage": self.leverage,
                "total_trades": len(self.trade_log),
                "strategies_tested": len([k for k, v in self.results.items() if v["events"] > 0]),
                "note": "Stop loss based on capital percentage, not price percentage",
            },
            "results": self.results,
        }
        
        with open(output_path, "w") as f:
            json.dump(output_data, f, indent=2, default=str)
        
        print(f"\n💾 结果已保存: {output_path}")


def main():
    print("🚀 BTC 做空策略深度回测 - 按本金百分比止损版本")
    print()
    
    tester = ShortStrategyBacktesterCapitalSL(initial_capital=10000, leverage=50)
    
    df = tester.load_data(months=5)
    
    if df.empty:
        print("❌ 无法加载数据，退出")
        return
    
    df = tester.prepare_features(df)
    
    results = tester.run_all(df)
    
    tester.print_report()
    
    tester.save_results()
    
    print("\n✅ 回测完成！")
    print("\n💡 关键改进：")
    print("   ✅ 止损按本金百分比计算（如10%本金止损）")
    print("   ✅ 自动根据杠杆调整价格止损位")
    print("   ✅ 更合理的风控设置")
    print()
    print("📊 止损计算公式：")
    print("   价格止损 = 本金止损 ÷ 杠杆倍数")
    print("   例如：10%本金止损 ÷ 50x杠杆 = 0.2%价格止损")


if __name__ == "__main__":
    main()
