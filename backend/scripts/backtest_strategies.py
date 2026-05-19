#!/usr/bin/env python3
"""
Playbooks 策略回测对比
"""

from pathlib import Path
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Dict, List

@dataclass
class Config:
    capital: float = 100000
    commission: float = 0.0005
    position_size: float = 0.3
    stop_loss: float = 0.015
    take_profit: float = 0.03
    max_hold: int = 4

def prepare(df):
    df = df.copy()
    df["return_1h"] = df["close"].pct_change(1)
    df["volume_ratio"] = df["volume"] / df["volume"].rolling(24).mean()
    df["intrabar_vol"] = (df["high"] - df["low"]) / df["close"]
    df["is_weekend"] = df["timestamp"].dt.dayofweek >= 5
    return df

def detect_panic(df, i):
    if i < 2: return False
    return df.iloc[i]["return_1h"] < -0.02 and df.iloc[i]["volume_ratio"] > 1.5

def detect_climax(df, i):
    if i < 2: return False
    return df.iloc[i]["volume_ratio"] > 2.0 and df.iloc[i]["intrabar_vol"] > 0.025

def detect_weekend(df, i):
    if i < 2: return False
    return df.iloc[i]["is_weekend"] and df.iloc[i]["volume_ratio"] < 0.8 and df.iloc[i]["intrabar_vol"] > 0.015

def detect_oi(df, i):
    if i < 2: return False
    r = df.iloc[i]
    return r["funding_rate"] > 0.0003 and r["volume_ratio"] > 2.0 and r["regime"] == "volatile"

def backtest(df, detectors, name, config):
    capital = float(config.capital)
    position = None
    trades = []
    equity_curve = []
    
    for i in range(1, len(df)):
        row = df.iloc[i]
        
        if position:
            elapsed = (row["timestamp"] - position["entry_time"]).total_seconds() / 3600
            pnl_pct = (row["close"] - position["entry"]) / position["entry"]
            
            exit_signal = (
                elapsed >= config.max_hold or
                pnl_pct >= config.take_profit or
                pnl_pct <= -config.stop_loss
            )
            
            if exit_signal:
                pos_value = capital * config.position_size * (1 + pnl_pct)
                pnl = pos_value - capital * config.position_size
                pnl -= capital * config.position_size * config.commission * 2
                capital = capital - capital * config.position_size + pos_value - capital * config.position_size * config.commission
                trades.append({"pnl": pnl, "reason": position["reason"], "pnl_pct": pnl_pct})
                position = None
        
        if not position:
            for reason, detect_fn in detectors:
                if detect_fn(df, i):
                    position = {
                        "entry": row["close"],
                        "entry_time": row["timestamp"],
                        "reason": reason
                    }
                    break
        
        equity = capital
        if position:
            equity = capital + capital * config.position_size * (row["close"] - position["entry"]) / position["entry"]
        equity_curve.append(equity)
    
    total_return = (capital - config.capital) / config.capital
    
    peak = config.capital
    max_dd = 0
    for e in equity_curve:
        if e > peak: peak = e
        dd = (peak - e) / peak
        if dd > max_dd: max_dd = dd
    
    wins = [t for t in trades if t["pnl"] > 0]
    win_rate = len(wins) / len(trades) if trades else 0
    
    total_pnl = sum(t["pnl"] for t in trades)
    
    return {
        "name": name,
        "return": total_return,
        "max_dd": max_dd,
        "win_rate": win_rate,
        "trades": len(trades),
        "total_pnl": total_pnl,
        "reason_pnl": {r: sum(t["pnl"] for t in trades if t["reason"] == r) for r in set(t["reason"] for t in trades)}
    }

def main():
    print("="*70)
    print("📊 Playbooks 策略回测对比")
    print("="*70)
    
    df = pd.read_parquet("data_lake/features/binance/BTCUSDT/features_with_structure.parquet")
    df = df.set_index("timestamp").resample("1h").agg({
        "open": "first", "high": "max", "low": "min", "close": "last",
        "volume": "sum", "funding_rate": "last", "regime": "last"
    }).dropna().reset_index()
    
    df_2024 = df[df["timestamp"].dt.year == 2024].copy()
    df_2024 = prepare(df_2024)
    print(f"数据: {len(df_2024)} 小时K线 (2024)")
    
    configs = [
        ("保守", Config(position_size=0.3, stop_loss=0.02, take_profit=0.04)),
        ("激进", Config(position_size=0.5, stop_loss=0.01, take_profit=0.06)),
        ("均衡", Config(position_size=0.4, stop_loss=0.015, take_profit=0.05)),
    ]
    
    strategies = [
        ("Panic Reversal", [("panic", detect_panic)]),
        ("Volume Climax", [("climax", detect_climax)]),
        ("Weekend", [("weekend", detect_weekend)]),
        ("OI Flush", [("oi", detect_oi)]),
        ("All 多头", [("panic", detect_panic), ("climax", detect_climax), ("weekend", detect_weekend), ("oi", detect_oi)]),
    ]
    
    results = []
    for name, detectors in strategies:
        for cfg_name, cfg in configs:
            result = backtest(df_2024, detectors, name, cfg)
            result["config"] = cfg_name
            results.append(result)
    
    print(f"\n{'='*75}")
    print(f"📈 策略对比")
    print("="*75)
    print(f"{'策略':<15} | {'配置':<6} | {'收益':>8} | {'最大回撤':>8} | {'胜率':>6} | {'交易数':>6}")
    print("-"*75)
    
    for r in sorted(results, key=lambda x: -x["return"]):
        print(f"{r['name']:<15} | {r['config']:<6} | {r['return']*100:>7.2f}% | {r['max_dd']*100:>7.2f}% | {r['win_rate']*100:>5.1f}% | {r['trades']:>6}")
    
    print(f"\n{'='*75}")
    print("📋 各策略收益分解")
    print("="*75)
    for r in sorted(results, key=lambda x: -x["return"]):
        if r["reason_pnl"]:
            print(f"\n{r['name']} ({r['config']}):")
            for reason, pnl in sorted(r["reason_pnl"].items(), key=lambda x: -x[1]):
                reason_name = {"panic": "Panic", "climax": "Climax", "weekend": "Weekend", "oi": "OI"}.get(reason, reason)
                print(f"   {reason_name}: ${pnl:,.2f}")
    
    print(f"\n{'='*75}")
    print("✅ 完成！")
    print("="*75)

if __name__ == "__main__":
    main()
