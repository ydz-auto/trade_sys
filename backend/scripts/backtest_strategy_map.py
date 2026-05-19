#!/usr/bin/env python3
"""
BTC 策略地图 - 12大策略综合回测

基于最近5个月数据，测试所有策略：
1. Panic Reversal - 恐慌下跌后的修复
2. Compression Breakout - 波动压缩后突破
3. Funding Reset - 高杠杆情绪清洗
4. Volume Climax Fade - 放量高潮后的回落
5. Weak Bounce Short - 弱反弹做空
6. OI Flush - 清杠杆后的下行延续
7. Short Squeeze Hunt - 抓空头挤压
8. Long Liquidation Bounce - 多头踩踏后反弹
9. Fake Breakout Trap - 假突破反杀
10. Weekend Liquidity Trap - 周末低流动性
11. Session Rotation - 时段套利
12. Macro Shock Recovery - 宏观事件冲击后的回归
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

logger = get_logger("strategy_map_backtest")


@dataclass
class StrategyConfig:
    name: str
    direction: int  # 1=做多, -1=做空
    detection: str
    key_features: List[str]
    stop_loss: float
    take_profit: float
    min_threshold: float


STRATEGIES = {
    "panic_reversal": StrategyConfig(
        name="Panic Reversal",
        direction=1,
        detection="1h下跌>1.5% + 放量",
        key_features=["returns_1h", "volume_ratio"],
        stop_loss=0.02,
        take_profit=0.03,
        min_threshold=-0.015,
    ),
    "compression_breakout": StrategyConfig(
        name="Compression Breakout",
        direction=1,
        detection="布林带收窄 + 突破",
        key_features=["bb_width", "breakout_strength_24h", "volume_ratio"],
        stop_loss=0.015,
        take_profit=0.025,
        min_threshold=0.003,
    ),
    "funding_reset": StrategyConfig(
        name="Funding Reset",
        direction=-1,
        detection="funding极端 + 开始回落",
        key_features=["funding_rate", "funding_delta"],
        stop_loss=0.02,
        take_profit=0.025,
        min_threshold=0.0005,
    ),
    "volume_climax_fade": StrategyConfig(
        name="Volume Climax Fade",
        direction=-1,
        detection="放量高潮 + 长上影",
        key_features=["volume_ratio", "wick_ratio", "returns_1h"],
        stop_loss=0.015,
        take_profit=0.02,
        min_threshold=2.5,
    ),
    "weak_bounce_short": StrategyConfig(
        name="Weak Bounce Short",
        direction=-1,
        detection="大跌后弱反弹",
        key_features=["returns_4h", "returns_1h", "volume_ratio"],
        stop_loss=0.02,
        take_profit=0.03,
        min_threshold=-0.03,
    ),
    "oi_flush": StrategyConfig(
        name="OI Flush",
        direction=-1,
        detection="OI大跌 + 价格未跌太多",
        key_features=["oi_change_1h", "returns_1h"],
        stop_loss=0.015,
        take_profit=0.025,
        min_threshold=-0.05,
    ),
    "short_squeeze_hunt": StrategyConfig(
        name="Short Squeeze Hunt",
        direction=1,
        detection="funding负 + OI增 + 突然拉升",
        key_features=["funding_rate", "oi_change_1h", "returns_1h"],
        stop_loss=0.02,
        take_profit=0.03,
        min_threshold=0.01,
    ),
    "long_liquidation_bounce": StrategyConfig(
        name="Long Liquidation Bounce",
        direction=1,
        detection="大跌 + 放量 + funding下降",
        key_features=["returns_1h", "volume_ratio", "funding_delta"],
        stop_loss=0.02,
        take_profit=0.04,
        min_threshold=-0.02,
    ),
    "fake_breakout_trap": StrategyConfig(
        name="Fake Breakout Trap",
        direction=-1,
        detection="突破前高 + 成交量不足",
        key_features=["breakout_strength_24h", "volume_ratio"],
        stop_loss=0.015,
        take_profit=0.02,
        min_threshold=0.01,
    ),
    "weekend_liquidity_trap": StrategyConfig(
        name="Weekend Liquidity Trap",
        direction=-1,
        detection="周末 + 低成交量 + 突破",
        key_features=["volume_ratio", "is_weekend", "breakout_strength_24h"],
        stop_loss=0.02,
        take_profit=0.025,
        min_threshold=0.005,
    ),
    "session_rotation_asia": StrategyConfig(
        name="Session Rotation (Asia→US)",
        direction=1,
        detection="亚洲盘低流动 + 美盘开盘",
        key_features=["session", "volume_ratio", "returns_1h"],
        stop_loss=0.015,
        take_profit=0.025,
        min_threshold=-0.01,
    ),
    "macro_shock_recovery": StrategyConfig(
        name="Macro Shock Recovery",
        direction=1,
        detection="极端大跌后企稳",
        key_features=["returns_4h", "volume_ratio"],
        stop_loss=0.025,
        take_profit=0.05,
        min_threshold=-0.05,
    ),
}


class StrategyMapBacktester:
    def __init__(self, initial_capital: float = 10000, leverage: float = 50):
        self.initial_capital = initial_capital
        self.leverage = leverage
        self.results = {}
    
    def load_data(self, months: int = 5) -> pd.DataFrame:
        data_path = backend_path / "data_lake/features/binance/BTCUSDT/features_with_structure.parquet"
        df = pd.read_parquet(data_path)
        
        cutoff = datetime.now() - timedelta(days=months * 30)
        df = df[df["timestamp"] >= pd.Timestamp(cutoff)].copy()
        
        df = df.sort_values("timestamp").reset_index(drop=True)
        
        logger.info(f"Loaded {len(df)} rows, date range: {df['timestamp'].min()} to {df['timestamp'].min()}")
        
        return df
    
    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        df["hour"] = df["timestamp"].dt.hour
        df["day_of_week"] = df["timestamp"].dt.dayofweek
        df["is_weekend"] = df["day_of_week"] >= 5
        
        df["session"] = df["hour"].apply(
            lambda h: "asia" if 0 <= h < 8 else ("europe" if 8 <= h < 16 else "us")
        )
        
        if "volume" in df.columns:
            df["volume_ratio"] = df["volume"] / df["volume"].rolling(288).mean()
        
        if "high" in df.columns and "close" in df.columns and "low" in df.columns:
            df["wick_ratio"] = (df["high"] - df["close"]) / (df["high"] - df["low"] + 0.001)
        
        df["returns_5m"] = df["close"].pct_change(1)
        df["returns_15m"] = df["close"].pct_change(3)
        df["returns_1h"] = df["close"].pct_change(12)
        df["returns_4h"] = df["close"].pct_change(48)
        
        df["funding_delta"] = df["funding_rate"].diff(12)
        
        return df
    
    def detect_panic_reversal(self, row: pd.Series) -> bool:
        return (row.get("returns_1h", 0) < -0.015 and 
                row.get("volume_ratio", 1) > 1.5)
    
    def detect_compression_breakout(self, row: pd.Series, prev_rows: pd.DataFrame) -> bool:
        if len(prev_rows) < 288:
            return False
        
        volatility = prev_rows["close"].pct_change().rolling(288).std()
        recent_vol = volatility.iloc[-1]
        avg_vol = volatility.mean()
        
        if recent_vol > avg_vol * 0.8:
            return False
        
        return row.get("breakout_strength_24h", 0) > 0.003 and row.get("volume_ratio", 1) > 1.2
    
    def detect_funding_reset(self, row: pd.Series) -> bool:
        return (abs(row.get("funding_rate", 0)) > 0.0005 and 
                row.get("funding_delta", 0) < -0.0001)
    
    def detect_volume_climax_fade(self, row: pd.Series) -> bool:
        return (row.get("volume_ratio", 1) > 2.5 and 
                row.get("wick_ratio", 0) > 0.4 and 
                abs(row.get("returns_5m", 0)) > 0.005)
    
    def detect_weak_bounce_short(self, row: pd.Series, prev_rows: pd.DataFrame) -> bool:
        if len(prev_rows) < 48:
            return False
        
        drop_4h = prev_rows["close"].iloc[-48] - prev_rows["close"].iloc[-1]
        drop_4h_pct = drop_4h / prev_rows["close"].iloc[-48]
        
        bounce_1h = row.get("returns_1h", 0)
        
        return drop_4h_pct > 0.03 and 0.005 < bounce_1h < 0.015
    
    def detect_oi_flush(self, row: pd.Series) -> bool:
        return (row.get("oi_change_1h", 0) < -0.05 and 
                abs(row.get("returns_1h", 0)) < 0.02)
    
    def detect_short_squeeze_hunt(self, row: pd.Series) -> bool:
        return (row.get("funding_rate", 0) < -0.0001 and 
                row.get("oi_change_1h", 0) > 0.02 and 
                row.get("returns_1h", 0) > 0.015)
    
    def detect_long_liquidation_bounce(self, row: pd.Series) -> bool:
        return (row.get("returns_1h", 0) < -0.02 and 
                row.get("volume_ratio", 1) > 2.5 and 
                row.get("funding_delta", 0) < 0)
    
    def detect_fake_breakout_trap(self, row: pd.Series, prev_rows: pd.DataFrame) -> bool:
        if len(prev_rows) < 24:
            return False
        
        rolling_high = prev_rows["high"].iloc[-24:].max()
        breakout = row.get("high", 0) > rolling_high * 1.01
        
        return breakout and row.get("volume_ratio", 1) < 1.0
    
    def detect_weekend_liquidity_trap(self, row: pd.Series, prev_rows: pd.DataFrame) -> bool:
        if len(prev_rows) < 24:
            return False
        
        rolling_high = prev_rows["high"].iloc[-24:].max()
        rolling_low = prev_rows["low"].iloc[-24:].min()
        
        breakout_up = row.get("high", 0) > rolling_high * 1.005
        breakout_down = row.get("low", 0) < rolling_low * 0.995
        
        return row.get("is_weekend", False) and row.get("volume_ratio", 1) < 0.7 and (breakout_up or breakout_down)
    
    def detect_session_rotation(self, row: pd.Series, prev_rows: pd.DataFrame) -> bool:
        if len(prev_rows) < 12:
            return False
        
        asia_low_vol = prev_rows["volume_ratio"].iloc[-12:].mean() < 0.8
        
        us_open = row.get("hour", 0) in [15, 16, 17]
        
        return asia_low_vol and us_open and row.get("returns_1h", 0) > -0.01
    
    def detect_macro_shock_recovery(self, row: pd.Series, prev_rows: pd.DataFrame) -> bool:
        if len(prev_rows) < 48:
            return False
        
        drop_4h = prev_rows["close"].iloc[-48] - prev_rows["close"].iloc[-1]
        drop_4h_pct = drop_4h / prev_rows["close"].iloc[-48]
        
        return drop_4h_pct > 0.05 and abs(row.get("returns_1h", 0)) < 0.005
    
    def run_backtest(self, df: pd.DataFrame) -> Dict:
        events_by_strategy = {k: [] for k in STRATEGIES}
        
        for i in range(288, len(df)):
            row = df.iloc[i]
            prev_rows = df.iloc[max(0, i-300):i]
            
            if self.detect_panic_reversal(row):
                events_by_strategy["panic_reversal"].append({
                    "timestamp": row["timestamp"],
                    "price": row["close"],
                    "direction": 1,
                    "features": {"returns_1h": row.get("returns_1h"), "volume_ratio": row.get("volume_ratio")}
                })
            
            if self.detect_volume_climax_fade(row):
                events_by_strategy["volume_climax_fade"].append({
                    "timestamp": row["timestamp"],
                    "price": row["close"],
                    "direction": -1,
                    "features": {"volume_ratio": row.get("volume_ratio"), "wick_ratio": row.get("wick_ratio")}
                })
            
            if self.detect_oi_flush(row):
                events_by_strategy["oi_flush"].append({
                    "timestamp": row["timestamp"],
                    "price": row["close"],
                    "direction": -1,
                    "features": {"oi_change": row.get("oi_change_1h"), "returns_1h": row.get("returns_1h")}
                })
            
            if self.detect_long_liquidation_bounce(row):
                events_by_strategy["long_liquidation_bounce"].append({
                    "timestamp": row["timestamp"],
                    "price": row["close"],
                    "direction": 1,
                    "features": {"returns_1h": row.get("returns_1h"), "volume_ratio": row.get("volume_ratio")}
                })
            
            if self.detect_short_squeeze_hunt(row):
                events_by_strategy["short_squeeze_hunt"].append({
                    "timestamp": row["timestamp"],
                    "price": row["close"],
                    "direction": 1,
                    "features": {"funding": row.get("funding_rate"), "oi_change": row.get("oi_change_1h")}
                })
            
            if self.detect_fake_breakout_trap(row, prev_rows):
                events_by_strategy["fake_breakout_trap"].append({
                    "timestamp": row["timestamp"],
                    "price": row["close"],
                    "direction": -1,
                    "features": {"volume_ratio": row.get("volume_ratio")}
                })
            
            if self.detect_weak_bounce_short(row, prev_rows):
                events_by_strategy["weak_bounce_short"].append({
                    "timestamp": row["timestamp"],
                    "price": row["close"],
                    "direction": -1,
                    "features": {"returns_1h": row.get("returns_1h")}
                })
            
            if self.detect_weekend_liquidity_trap(row, prev_rows):
                events_by_strategy["weekend_liquidity_trap"].append({
                    "timestamp": row["timestamp"],
                    "price": row["close"],
                    "direction": -1,
                    "features": {"volume_ratio": row.get("volume_ratio")}
                })
            
            if self.detect_funding_reset(row):
                events_by_strategy["funding_reset"].append({
                    "timestamp": row["timestamp"],
                    "price": row["close"],
                    "direction": -1,
                    "features": {"funding_rate": row.get("funding_rate"), "funding_delta": row.get("funding_delta")}
                })
            
            if self.detect_session_rotation(row, prev_rows):
                events_by_strategy["session_rotation_asia"].append({
                    "timestamp": row["timestamp"],
                    "price": row["close"],
                    "direction": 1,
                    "features": {"session": row.get("session")}
                })
            
            if self.detect_macro_shock_recovery(row, prev_rows):
                events_by_strategy["macro_shock_recovery"].append({
                    "timestamp": row["timestamp"],
                    "price": row["close"],
                    "direction": 1,
                    "features": {"returns_4h": row.get("returns_4h")}
                })
            
            if self.detect_compression_breakout(row, prev_rows):
                events_by_strategy["compression_breakout"].append({
                    "timestamp": row["timestamp"],
                    "price": row["close"],
                    "direction": 1,
                    "features": {"bb_width": row.get("bb_width"), "breakout": row.get("breakout_strength_24h")}
                })
        
        return events_by_strategy
    
    def compute_outcomes(self, events: List[Dict], df: pd.DataFrame) -> List[Dict]:
        outcomes = []
        
        for event in events:
            event_time = event["timestamp"]
            entry_price = event["price"]
            direction = event["direction"]
            
            entry_idx = df[df["timestamp"] == event_time].index
            if len(entry_idx) == 0:
                continue
            
            idx = entry_idx[0]
            
            future_1h_idx = min(idx + 60, len(df) - 1)
            future_4h_idx = min(idx + 240, len(df) - 1)
            
            if future_1h_idx <= idx:
                continue
            
            exit_1h_price = df.iloc[future_1h_idx]["close"]
            exit_4h_price = df.iloc[future_4h_idx]["close"]
            
            ret_1h = ((exit_1h_price - entry_price) / entry_price) * direction * self.leverage
            ret_4h = ((exit_4h_price - entry_price) / entry_price) * direction * self.leverage
            
            outcomes.append({
                "timestamp": event_time,
                "direction": direction,
                "ret_1h": ret_1h,
                "ret_4h": ret_4h,
                "features": event["features"]
            })
        
        return outcomes
    
    def run_all(self, df: pd.DataFrame) -> Dict:
        logger.info("Running backtest...")
        
        events = self.run_backtest(df)
        
        results = {}
        
        for strategy_key, strategy_events in events.items():
            config = STRATEGIES.get(strategy_key)
            if not config:
                continue
            
            outcomes = self.compute_outcomes(strategy_events, df)
            
            if not outcomes:
                results[strategy_key] = {
                    "name": config.name,
                    "direction": "做多" if config.direction == 1 else "做空",
                    "events": 0,
                    "win_rate_1h": 0,
                    "avg_ret_1h": 0,
                    "avg_ret_4h": 0,
                    "best_ret": 0,
                    "worst_ret": 0,
                    "liquidation_count": 0,
                }
                continue
            
            rets_1h = [o["ret_1h"] for o in outcomes]
            rets_4h = [o["ret_4h"] for o in outcomes]
            
            wins_1h = sum(1 for r in rets_1h if r > 0)
            liquidations = sum(1 for r in rets_1h if r < -0.02)
            
            results[strategy_key] = {
                "name": config.name,
                "direction": "做多" if config.direction == 1 else "做空",
                "events": len(outcomes),
                "win_rate_1h": wins_1h / len(outcomes) if outcomes else 0,
                "avg_ret_1h": np.mean(rets_1h) if rets_1h else 0,
                "avg_ret_4h": np.mean(rets_4h) if rets_4h else 0,
                "best_ret": max(rets_1h) if rets_1h else 0,
                "worst_ret": min(rets_1h) if rets_1h else 0,
                "liquidation_count": liquidations,
                "liquidation_rate": liquidations / len(outcomes) if outcomes else 0,
            }
        
        return results
    
    def print_report(self, results: Dict):
        print("\n" + "=" * 100)
        print("📊 BTC 策略地图 - 12大策略回测报告（近5个月）")
        print("=" * 100)
        print(f"初始资金: ${self.initial_capital:,.0f} | 杠杆: {self.leverage}x")
        print()
        
        print(f"{'策略':<25} | {'方向':<6} | {'样本':<6} | {'胜率':<8} | {'1h收益':<12} | {'4h收益':<12} | {'最佳':<10} | {'最差':<10} | {'爆仓':<6}")
        print("-" * 100)
        
        sorted_results = sorted(
            results.items(),
            key=lambda x: -(x[1]["avg_ret_1h"] * x[1]["events"])
        )
        
        for key, r in sorted_results:
            if r["events"] == 0:
                continue
            
            win_rate_str = f"{r['win_rate_1h']*100:.1f}%"
            avg_1h_str = f"{r['avg_ret_1h']*100:+.2f}%"
            avg_4h_str = f"{r['avg_ret_4h']*100:+.2f}%"
            best_str = f"{r['best_ret']*100:+.1f}%"
            worst_str = f"{r['worst_ret']*100:+.1f}%"
            liq_str = f"{r['liquidation_count']}({r['liquidation_rate']*100:.1f}%)"
            
            print(f"{r['name']:<25} | {r['direction']:<6} | {r['events']:<6} | {win_rate_str:<8} | {avg_1h_str:>10} | {avg_4h_str:>10} | {best_str:>8} | {worst_str:>8} | {liq_str}")
        
        print()
        print("=" * 100)
        print("🏆 TOP 5 策略（按1h收益×样本数排序）")
        print("=" * 100)
        
        for i, (key, r) in enumerate(sorted_results[:5], 1):
            if r["events"] == 0:
                continue
            
            expected = r["avg_ret_1h"] * self.initial_capital * r["events"]
            print(f"  {i}. {r['name']}: {r['events']}笔交易, 胜率{r['win_rate_1h']*100:.1f}%, 1h收益{r['avg_ret_1h']*100:+.2f}%, 预期收益${expected:+,.0f}")
        
        print()
        print("=" * 100)
        print("❌ 未触发策略")
        print("=" * 100)
        
        for key, r in results.items():
            if r["events"] == 0:
                print(f"  - {r['name']}: 未检测到事件")


def main():
    print("🚀 BTC 策略地图回测 - 12大策略")
    print()
    
    tester = StrategyMapBacktester(initial_capital=10000, leverage=50)
    
    df = tester.load_data(months=5)
    
    df = tester.prepare_features(df)
    
    results = tester.run_all(df)
    
    tester.print_report(results)
    
    output_path = backend_path / "data_lake/research/strategy_map_5months.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n💾 结果已保存: {output_path}")


if __name__ == "__main__":
    main()
