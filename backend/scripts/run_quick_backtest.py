#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整策略回测 - 快速版
运行所有39个策略在4个交易对上
"""

import sys
from pathlib import Path

script_dir = Path(__file__).parent
backend_path = script_dir.parent
sys.path.insert(0, str(backend_path))

import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict

print("=" * 120)
print("🚀 完整策略回测系统 - 39个策略, 4个交易对")
print("=" * 120)

# 配置
INITIAL_CAPITAL = 10000.0
LEVERAGE = 50.0
MAX_CAPITAL_SL = 0.10  # 10% 资金止损
TRAILING_STOP = 0.15   # 15% 移动止损
FIXED_TP = 0.20        # 20% 固定止盈
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "ZECUSDT"]

print(f"📊 配置:")
print(f"   初始资金: ${INITIAL_CAPITAL:,.2f}")
print(f"   杠杆倍数: {LEVERAGE}x")
print(f"   最大资金止损: {MAX_CAPITAL_SL*100:.0f}%")
print(f"   移动止损回撤: {TRAILING_STOP*100:.0f}%")
print(f"   固定止盈: {FIXED_TP*100:.0f}%")
print(f"   交易对: {', '.join(SYMBOLS)}")
print("=" * 120)

# 策略定义
STRATEGIES = {
    "rsi_14": {"name": "RSI超买超卖", "desc": "RSI < 30做多, RSI > 70做空"},
    "macd_12_26_9": {"name": "MACD金叉死叉", "desc": "MACD金叉做多, 死叉做空"},
    "bollinger_bands": {"name": "布林带突破", "desc": "突破上轨做空, 跌破下轨做多"},
    "ma_cross": {"name": "均线交叉", "desc": "MA50/MA200交叉"},
    "rsi_macd_combo": {"name": "RSI+MACD组合", "desc": "RSI+MACD联合信号"},
    "ema_cross": {"name": "EMA交叉", "desc": "EMA20/EMA50交叉"},
    
    "panic_reversal": {"name": "恐慌反弹", "desc": "大跌+放量反弹"},
    "long_liquidation_bounce": {"name": "多头踩踏", "desc": "大跌+RSI超卖+放量"},
    "volume_climax_fade": {"name": "放量衰竭", "desc": "放量新高衰竭做空"},
    "weak_bounce_short": {"name": "弱反弹", "desc": "大跌后弱反弹做空"},
    "fake_breakout_trap": {"name": "假突破", "desc": "突破但量能不足"},
    "short_squeeze_hunt": {"name": "空头挤压", "desc": "负资金费率+OI上涨"},
    
    "compression_breakout": {"name": "压缩突破", "desc": "布林带压缩后突破"},
    "funding_reset": {"name": "资金费重置", "desc": "极高资金费后回归"},
    "oi_flush": {"name": "OI洗盘", "desc": "OI快速下降"},
    "weekend_liquidity_trap": {"name": "周末陷阱", "desc": "周末流动性陷阱"},
    "session_rotation": {"name": "时段轮换", "desc": "亚洲到欧美时段"},
    "macro_shock_recovery": {"name": "宏观冲击恢复", "desc": "大跌后恢复"},
    
    "leveraged_short_squeeze": {"name": "杠杆空头挤压", "desc": "高资金费+量能放大"},
    "micro_range_ripples": {"name": "微区间涟漪", "desc": "小区间内波动"},
    "cascade_flip": {"name": "级联翻转", "desc": "量能级联变化"},
    "funding_exhaustion_trap": {"name": "资金费衰竭", "desc": "资金费极端值"},
    "meme_mania_rotation": {"name": "Meme狂热", "desc": "社交情绪驱动"},
    "session_gap_exploit": {"name": "开盘跳空", "desc": "时段开盘跳空"},
    "dead_cat_echo": {"name": "死猫反弹", "desc": "大跌后有限反弹"},
    "liquidity_vacuum_breakout": {"name": "流动性真空", "desc": "低流动性突破"},
    
    "pb_panic_reversal": {"name": "Playbook恐慌", "desc": "放宽版恐慌"},
    "pb_fake_breakout": {"name": "Playbook假突破", "desc": "放宽版假突破"},
    "pb_oi_flush": {"name": "Playbook OI", "desc": "放宽版OI洗盘"},
    "pb_weekend_manipulation": {"name": "Playbook周末", "desc": "周末操纵"},
    "pb_short_squeeze": {"name": "Playbook空头挤压", "desc": "放宽版空头挤压"},
    "pb_volume_climax": {"name": "Playbook放量", "desc": "放宽版放量"},
    "pb_liquidation_cascade": {"name": "Playbook清盘", "desc": "清盘级联"},
    
    "v2_volume_climax_fade": {"name": "V2放量衰竭", "desc": "优化版放量"},
    "v2_weak_bounce_short": {"name": "V2弱反弹", "desc": "优化版弱反弹"},
    "v2_fake_breakout_trap": {"name": "V2假突破", "desc": "优化版假突破"},
    "v2_weekend_trap": {"name": "V2周末陷阱", "desc": "优化版周末"},
    "v2_short_squeeze_hunt": {"name": "V2空头挤压", "desc": "优化版空头挤压"},
    "v2_funding_reset": {"name": "V2资金费", "desc": "优化版资金费"},
}

print(f"\n📋 策略数: {len(STRATEGIES)} 个")

def generate_mock_data(symbol, days=120):
    """生成模拟数据"""
    base_prices = {
        "BTCUSDT": 65000, "ETHUSDT": 3500, "SOLUSDT": 150, "ZECUSDT": 60
    }
    base_price = base_prices.get(symbol, 100)
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)
    periods = int((end_time - start_time).total_seconds() / (5 * 60))
    
    np.random.seed(hash(symbol) % 10000)
    timestamps = pd.date_range(start=start_time, end=end_time, periods=periods)
    
    # 生成带漂移和波动的价格
    returns = np.random.normal(0.00008, 0.0045, periods)
    prices = base_price * (1 + returns).cumprod()
    
    # 添加一些极端行情
    crash_indices = np.random.choice(periods, size=6, replace=False)
    for idx in crash_indices:
        prices[max(0, idx-6):min(periods, idx+6)] *= 0.95
    
    df = pd.DataFrame({
        "timestamp": timestamps,
        "open": prices * (1 + np.random.normal(0, 0.0015, periods)),
        "high": prices * (1 + np.random.uniform(0, 0.008, periods)),
        "low": prices * (1 - np.random.uniform(0, 0.008, periods)),
        "close": prices,
        "volume": np.random.uniform(800, 15000, periods),
        "symbol": symbol,
    })
    
    # 计算技术指标
    df["returns_1h"] = df["close"].pct_change(12)
    df["returns_4h"] = df["close"].pct_change(48)
    
    # RSI
    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-10)
    df["rsi_14"] = 100 - (100 / (1 + rs))
    
    # 布林带
    df["bb_middle"] = df["close"].rolling(window=20).mean()
    df["bb_std"] = df["close"].rolling(window=20).std()
    df["bb_upper"] = df["bb_middle"] + 2 * df["bb_std"]
    df["bb_lower"] = df["bb_middle"] - 2 * df["bb_std"]
    df["bb_position"] = (df["close"] - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"] + 1e-10)
    
    # MACD
    ema12 = df["close"].ewm(span=12).mean()
    ema26 = df["close"].ewm(span=26).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9).mean()
    
    # 成交量比率
    df["volume_ratio"] = df["volume"] / df["volume"].rolling(288).mean()
    
    # 模拟资金费率
    df["funding_rate"] = np.random.normal(0.0001, 0.0003, periods)
    df["funding_delta"] = df["funding_rate"].diff(12)
    
    # OI变化
    df["oi_change_1h"] = np.random.normal(0, 0.018, periods)
    
    # 上影线
    df["wick_ratio"] = (df["high"] - df["close"]) / (df["high"] - df["low"] + 0.001)
    
    return df.dropna()

class Position:
    def __init__(self, strategy_id, symbol, direction, entry_price, entry_time, margin):
        self.strategy_id = strategy_id
        self.symbol = symbol
        self.direction = direction
        self.entry_price = entry_price
        self.entry_time = entry_time
        self.margin = margin
        self.highest_price = entry_price
        self.lowest_price = entry_price
        self.stop_loss_price = self._calc_sl(entry_price)
        self.trailing_stop_price = self.stop_loss_price
        self.take_profit_price = self._calc_tp(entry_price)
    
    def _calc_sl(self, price):
        sl_pct = MAX_CAPITAL_SL / LEVERAGE
        if self.direction == "long":
            return price * (1 - sl_pct)
        else:
            return price * (1 + sl_pct)
    
    def _calc_tp(self, price):
        if not FIXED_TP:
            return None
        tp_pct = FIXED_TP / LEVERAGE
        if self.direction == "long":
            return price * (1 + tp_pct)
        else:
            return price * (1 - tp_pct)
    
    def update(self, row):
        if self.direction == "long":
            if row["high"] > self.highest_price:
                self.highest_price = row["high"]
                ts_pct = TRAILING_STOP / LEVERAGE
                new_ts = self.highest_price * (1 - ts_pct)
                if new_ts > self.trailing_stop_price:
                    self.trailing_stop_price = new_ts
        else:
            if row["low"] < self.lowest_price:
                self.lowest_price = row["low"]
                ts_pct = TRAILING_STOP / LEVERAGE
                new_ts = self.lowest_price * (1 + ts_pct)
                if new_ts < self.trailing_stop_price:
                    self.trailing_stop_price = new_ts
    
    def check_close(self, row):
        close_reason = None
        exit_price = row["close"]
        
        if self.direction == "long":
            if row["low"] <= self.stop_loss_price:
                close_reason = "stop_loss"
                exit_price = self.stop_loss_price
        else:
            if row["high"] >= self.stop_loss_price:
                close_reason = "stop_loss"
                exit_price = self.stop_loss_price
        
        if not close_reason and self.take_profit_price:
            if self.direction == "long":
                if row["high"] >= self.take_profit_price:
                    close_reason = "take_profit"
                    exit_price = self.take_profit_price
            else:
                if row["low"] <= self.take_profit_price:
                    close_reason = "take_profit"
                    exit_price = self.take_profit_price
        
        if not close_reason:
            if self.direction == "long":
                if row["low"] <= self.trailing_stop_price:
                    close_reason = "trailing_stop"
                    exit_price = self.trailing_stop_price
            else:
                if row["high"] >= self.trailing_stop_price:
                    close_reason = "trailing_stop"
                    exit_price = self.trailing_stop_price
        
        return close_reason, exit_price
    
    def calculate_pnl(self, exit_price):
        if self.direction == "long":
            ret = (exit_price - self.entry_price) / self.entry_price
        else:
            ret = (self.entry_price - exit_price) / self.entry_price
        return ret * LEVERAGE * self.margin

def detect_signal(strategy_id, row, prev_rows):
    """检测策略信号"""
    signals = []
    rsi = row.get("rsi_14", 50)
    macd = row.get("macd", 0)
    macd_signal = row.get("macd_signal", 0)
    bb_pos = row.get("bb_position", 0.5)
    returns_1h = row.get("returns_1h", 0)
    volume_ratio = row.get("volume_ratio", 1)
    wick_ratio = row.get("wick_ratio", 0)
    
    if "rsi" in strategy_id:
        if rsi < 30:
            signals.append(("long", 0.7))
        elif rsi > 70:
            signals.append(("short", 0.7))
    
    if "macd" in strategy_id:
        if macd > macd_signal and macd > 0:
            signals.append(("long", 0.6))
        elif macd < macd_signal and macd < 0:
            signals.append(("short", 0.6))
    
    if "bollinger" in strategy_id:
        if bb_pos < 0:
            signals.append(("long", 0.6))
        elif bb_pos > 1:
            signals.append(("short", 0.6))
    
    if "panic" in strategy_id or "liquidation" in strategy_id:
        if returns_1h < -0.015 and volume_ratio > 1.5:
            signals.append(("long", 0.75))
    
    if "volume" in strategy_id and "fade" in strategy_id:
        if volume_ratio > 2.0 and wick_ratio > 0.3 and returns_1h > 0.003:
            signals.append(("short", 0.7))
    
    if "weak" in strategy_id:
        if len(prev_rows) >= 48:
            returns_4h = row.get("returns_4h", 0)
            if returns_4h < -0.02 and 0.003 < returns_1h < 0.015 and volume_ratio > 1.5:
                signals.append(("short", 0.65))
    
    if "fake" in strategy_id:
        if len(prev_rows) >= 24:
            rolling_high = prev_rows["high"].iloc[-24:].max()
            if row["high"] > rolling_high * 1.005 and volume_ratio < 1.2:
                signals.append(("short", 0.65))
    
    if "short" in strategy_id and "squeeze" in strategy_id:
        funding_rate = row.get("funding_rate", 0)
        oi_change = row.get("oi_change_1h", 0)
        if funding_rate < -0.00005 and oi_change > 0.01 and returns_1h > 0.008:
            signals.append(("long", 0.7))
    
    if "funding" in strategy_id:
        funding_rate = row.get("funding_rate", 0)
        if abs(funding_rate) > 0.0003:
            if funding_rate > 0:
                signals.append(("short", 0.6))
            else:
                signals.append(("long", 0.6))
    
    if "oi" in strategy_id:
        oi_change = row.get("oi_change_1h", 0)
        if oi_change < -0.05:
            signals.append(("short", 0.55))
    
    if "compression" in strategy_id or "micro" in strategy_id:
        bb_width = row.get("bb_std", 0)
        if bb_width and bb_width < 0.015 and volume_ratio > 1.2:
            signals.append(("long", 0.5))
    
    if "dead_cat" in strategy_id:
        if len(prev_rows) >= 48:
            returns_4h = row.get("returns_4h", 0)
            if returns_4h < -0.03 and 0.005 < returns_1h < 0.015 and volume_ratio < 1.0:
                signals.append(("short", 0.6))
    
    if "v2" in strategy_id:
        if volume_ratio > 1.8 and wick_ratio > 0.25:
            if returns_1h > 0.005:
                signals.append(("short", 0.65))
    
    if not signals:
        if strategy_id in ["pb_panic_reversal", "pb_volume_climax"]:
            if returns_1h < -0.01 and volume_ratio > 1.3:
                signals.append(("long", 0.6))
        elif strategy_id in ["pb_fake_breakout", "pb_oi_flush"]:
            if volume_ratio > 1.5 and returns_1h > 0.01:
                signals.append(("short", 0.55))
    
    return signals

def run_single_backtest(symbol, df):
    """运行单个交易对回测"""
    print(f"\n📊 回测 {symbol} - {len(df)} 行数据")
    
    positions = {}
    strategy_capitals = {sid: INITIAL_CAPITAL for sid in STRATEGIES.keys()}
    strategy_trades = defaultdict(list)
    all_trades = []
    
    for i in range(300, len(df)):
        row = df.iloc[i]
        prev_rows = df.iloc[max(0, i-300):i]
        current_time = row["timestamp"]
        
        # 检查持仓
        to_close = []
        for strategy_id, pos in list(positions.items()):
            pos.update(row)
            close_reason, exit_price = pos.check_close(row)
            
            if close_reason:
                pnl = pos.calculate_pnl(exit_price)
                duration = (current_time - pos.entry_time).total_seconds() / 3600
                
                trade = {
                    "strategy_id": strategy_id,
                    "symbol": symbol,
                    "direction": pos.direction,
                    "entry_time": pos.entry_time.isoformat(),
                    "exit_time": current_time.isoformat(),
                    "entry_price": pos.entry_price,
                    "exit_price": exit_price,
                    "margin": pos.margin,
                    "pnl": pnl,
                    "pnl_pct": (pnl / pos.margin) * 100,
                    "exit_reason": close_reason,
                    "duration_hours": duration,
                }
                
                to_close.append(strategy_id)
                all_trades.append(trade)
                strategy_trades[strategy_id].append(trade)
                strategy_capitals[strategy_id] += pnl
        
        for sid in to_close:
            del positions[sid]
        
        # 检查新信号
        for strategy_id in STRATEGIES.keys():
            if strategy_id in positions:
                continue
            
            signals = detect_signal(strategy_id, row, prev_rows)
            if signals:
                direction, confidence = signals[0]
                margin = strategy_capitals[strategy_id] * 0.95
                
                positions[strategy_id] = Position(
                    strategy_id, symbol, direction, 
                    row["close"], current_time, margin
                )
    
    # 平剩余仓位
    for strategy_id, pos in list(positions.items()):
        exit_price = df.iloc[-1]["close"]
        pnl = pos.calculate_pnl(exit_price)
        
        trade = {
            "strategy_id": strategy_id,
            "symbol": symbol,
            "direction": pos.direction,
            "entry_time": pos.entry_time.isoformat(),
            "exit_time": df.iloc[-1]["timestamp"].isoformat(),
            "entry_price": pos.entry_price,
            "exit_price": exit_price,
            "margin": pos.margin,
            "pnl": pnl,
            "pnl_pct": (pnl / pos.margin) * 100,
            "exit_reason": "end_of_data",
            "duration_hours": 0,
        }
        
        all_trades.append(trade)
        strategy_trades[strategy_id].append(trade)
        strategy_capitals[strategy_id] += pnl
    
    # 计算结果
    symbol_results = {}
    for strategy_id in STRATEGIES.keys():
        trades = strategy_trades[strategy_id]
        final_capital = strategy_capitals[strategy_id]
        
        if trades:
            wins = [t for t in trades if t["pnl"] > 0]
            total_return = final_capital - INITIAL_CAPITAL
            win_rate = len(wins) / len(trades) if trades else 0
            
            symbol_results[strategy_id] = {
                "final_capital": final_capital,
                "total_return": total_return,
                "return_pct": (total_return / INITIAL_CAPITAL) * 100,
                "total_trades": len(trades),
                "winning_trades": len(wins),
                "win_rate": win_rate * 100,
            }
        else:
            symbol_results[strategy_id] = {
                "final_capital": INITIAL_CAPITAL,
                "total_return": 0,
                "return_pct": 0,
                "total_trades": 0,
                "winning_trades": 0,
                "win_rate": 0,
            }
    
    return symbol_results, all_trades

# 运行所有交易对
print(f"\n🚀 开始运行回测...")
all_results = {}
all_trades = []

for symbol in SYMBOLS:
    print(f"\n⏳ 处理 {symbol}...")
    df = generate_mock_data(symbol)
    symbol_results, symbol_trades = run_single_backtest(symbol, df)
    all_results[symbol] = symbol_results
    all_trades.extend(symbol_trades)

# 汇总结果
print(f"\n{'='*120}")
print(f"📊 回测完成 - 汇总结果")
print(f"{'='*120}")

# 按策略汇总
strategy_summary = defaultdict(lambda: {
    "total_return": 0, "total_trades": 0, "winning_trades": 0, "symbols": set()
})

for symbol, results in all_results.items():
    for strategy_id, strat_res in results.items():
        s = strategy_summary[strategy_id]
        s["total_return"] += strat_res["total_return"]
        s["total_trades"] += strat_res["total_trades"]
        s["winning_trades"] += strat_res["winning_trades"]
        s["symbols"].add(symbol)

# 打印策略排名
print(f"\n🏆 策略综合排名 (按总收益):")
print(f"{'='*120}")
print(f"{'策略':<30} | {'交易对':<8} | {'交易数':<8} | {'胜率':<8} | {'总收益':<15} | {'年化':<8}")
print(f"{'-'*120}")

ranked_strategies = sorted(strategy_summary.items(), key=lambda x: x[1]["total_return"], reverse=True)

for strategy_id, summary in ranked_strategies:
    if summary["total_trades"] == 0:
        continue
    
    win_rate = summary["winning_trades"] / summary["total_trades"] * 100
    total_return = summary["total_return"]
    annualized = (total_return / (4 * 120 / 365)) / INITIAL_CAPITAL * 100  # 假设4个月
    
    status = "✅" if total_return > 0 else "❌"
    print(f"{status} {STRATEGIES[strategy_id]['name']:<28} | {len(summary['symbols']):<8} | {summary['total_trades']:<8} | {win_rate:>6.1f}% | ${total_return:>12,.2f} | {annualized:>6.1f}%")

# 各交易对最佳策略
print(f"\n📈 各交易对最佳策略:")
print(f"{'='*120}")

for symbol in SYMBOLS:
    results = all_results[symbol]
    best_strat = max(results.items(), key=lambda x: x[1]["total_return"])
    strat_id, strat_res = best_strat
    print(f"   {symbol:10} | {STRATEGIES[strat_id]['name']:<30} | 收益: ${strat_res['total_return']:>10,.2f} ({strat_res['return_pct']:>5.1f}%)")

# 保存结果
output_dir = backend_path / "data_lake" / "research"
output_dir.mkdir(parents=True, exist_ok=True)

output_data = {
    "config": {
        "initial_capital": INITIAL_CAPITAL,
        "leverage": LEVERAGE,
        "symbols": SYMBOLS,
    },
    "results": all_results,
    "summary": {
        strategy_id: {
            "total_return": s["total_return"],
            "total_trades": s["total_trades"],
            "winning_trades": s["winning_trades"],
            "symbols": list(s["symbols"]),
        }
        for strategy_id, s in strategy_summary.items()
    },
}

output_path = output_dir / "complete_backtest_results.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(output_data, f, indent=2, ensure_ascii=False)

print(f"\n💾 结果已保存: {output_path}")
print(f"\n{'='*120}")
print("✅ 回测完成!")
print(f"{'='*120}")

print(f"\n📊 总结:")
profitable_count = sum(1 for s in strategy_summary.values() if s["total_return"] > 0)
print(f"   总策略数: {len(STRATEGIES)}")
print(f"   盈利策略: {profitable_count}")
print(f"   总交易数: {len(all_trades)}")

