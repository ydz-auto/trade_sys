#!/usr/bin/env python3
"""
完整策略回测 - 系统内所有策略
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
print("🚀 完整策略回测系统")
print("=" * 120)

# 配置
INITIAL_CAPITAL = 10000.0
LEVERAGE = 50.0
MAX_CAPITAL_SL = 0.10  # 10% 资金止损
TRAILING_STOP = 0.15   # 15% 移动止损（资金）
FIXED_TP = 0.20        # 20% 固定止盈（资金）

print(f"📊 配置:")
print(f"   初始资金: ${INITIAL_CAPITAL:,.2f}")
print(f"   杠杆倍数: {LEVERAGE}x")
print(f"   最大资金止损: {MAX_CAPITAL_SL*100:.0f}%")
print(f"   移动止损回撤: {TRAILING_STOP*100:.0f}%")
print(f"   固定止盈: {FIXED_TP*100:.0f}%")
print(f"   时间周期: 5分钟")
print("=" * 120)

# 策略列表
STRATEGIES = {
    # 经典技术指标
    "rsi_14": {"name": "RSI超买超卖", "desc": "RSI < 30做多, RSI > 70做空"},
    "macd_12_26_9": {"name": "MACD金叉死叉", "desc": "MACD金叉做多, 死叉做空"},
    "bollinger_bands": {"name": "布林带突破", "desc": "突破上轨做空, 跌破下轨做多"},
    
    # 事件驱动策略
    "panic_reversal": {"name": "恐慌反弹", "desc": "1小时大跌+放量后做多"},
    "long_liquidation_bounce": {"name": "多头踩踏反弹", "desc": "大跌+RSI超卖+放量后做多"},
    "volume_climax_fade": {"name": "放量高潮衰竭", "desc": "放量大涨后做空"},
    "weak_bounce_short": {"name": "弱反弹做空", "desc": "大跌后弱反弹做空"},
    "fake_breakout_trap": {"name": "假突破反杀", "desc": "突破24小时高但放量不足，做空"},
    "short_squeeze_hunt": {"name": "空头挤压", "desc": "负资金费率+OI增加+上涨，做多"},
    "funding_reset": {"name": "资金费率重置", "desc": "极高资金费率后下降，做空"},
    "oi_flush": {"name": "OI洗盘", "desc": "OI快速减少但价格稳定，做空"},
    
    # Playbook策略
    "pb_panic_reversal": {"name": "Playbook恐慌反弹", "desc": "恐慌反弹（放宽条件）"},
    "pb_fake_breakout": {"name": "Playbook假突破", "desc": "假突破反杀（放宽条件）"},
    "pb_oi_flush": {"name": "PlaybookOI洗盘", "desc": "OI洗盘（放宽条件）"},
    "pb_short_squeeze": {"name": "Playbook空头挤压", "desc": "空头挤压（放宽条件）"},
    "pb_volume_climax": {"name": "Playbook放量高潮", "desc": "放量高潮（放宽条件）"},
}

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "ZECUSDT"]

print(f"\n📋 策略列表: {len(STRATEGIES)} 个策略")
print(f"📋 交易对: {', '.join(SYMBOLS)}")

def generate_mock_data(symbol, days=150):
    """生成模拟数据用于测试"""
    base_prices = {
        "BTCUSDT": 65000,
        "ETHUSDT": 3500,
        "SOLUSDT": 150,
        "ZECUSDT": 60,
    }
    
    base_price = base_prices.get(symbol, 100)
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)
    
    periods = int((end_time - start_time).total_seconds() / (5 * 60))
    
    np.random.seed(42 + hash(symbol) % 1000)
    
    timestamps = pd.date_range(start=start_time, end=end_time, periods=periods)
    
    # 生成价格序列
    returns = np.random.normal(0.0001, 0.004, periods)
    prices = base_price * (1 + returns).cumprod()
    
    # 添加一些极端行情
    crash_days = np.random.choice(periods, size=8, replace=False)
    prices[crash_days] *= 0.93
    rally_days = np.random.choice(periods, size=8, replace=False)
    prices[rally_days] *= 1.07
    
    df = pd.DataFrame({
        "timestamp": timestamps,
        "open": prices * (1 + np.random.normal(0, 0.001, periods)),
        "high": prices * (1 + np.random.uniform(0, 0.006, periods)),
        "low": prices * (1 - np.random.uniform(0, 0.006, periods)),
        "close": prices,
        "volume": np.random.uniform(1000, 10000, periods),
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
    
    # 成交量
    df["volume_ratio"] = df["volume"] / df["volume"].rolling(window=288).mean()
    
    # 模拟资金费率
    df["funding_rate"] = np.random.normal(0.0001, 0.0002, periods)
    df["funding_delta"] = df["funding_rate"].diff(12)
    
    # 模拟OI变化
    df["oi_change_1h"] = np.random.normal(0, 0.015, periods)
    
    # 上影线比例
    df["wick_ratio"] = (df["high"] - df["close"]) / (df["high"] - df["low"] + 0.001)
    
    return df

def detect_signal(strategy_id, row, prev_rows):
    """检测策略信号"""
    signals = []
    
    # RSI
    if strategy_id == "rsi_14":
        rsi = row.get("rsi_14", 50)
        if pd.notna(rsi):
            if rsi < 30:
                signals.append(("long", 0.7))
            elif rsi > 70:
                signals.append(("short", 0.7))
    
    # MACD
    elif strategy_id == "macd_12_26_9":
        macd = row.get("macd", 0)
        macd_signal = row.get("macd_signal", 0)
        if pd.notna(macd) and pd.notna(macd_signal):
            if macd > macd_signal and macd > 0:
                signals.append(("long", 0.7))
            elif macd < macd_signal and macd < 0:
                signals.append(("short", 0.7))
    
    # Bollinger Bands
    elif strategy_id == "bollinger_bands":
        bb_pos = row.get("bb_position", 0.5)
        if pd.notna(bb_pos):
            if bb_pos < 0:
                signals.append(("long", 0.6))
            elif bb_pos > 1:
                signals.append(("short", 0.6))
    
    # Panic Reversal
    elif strategy_id == "panic_reversal":
        returns_1h = row.get("returns_1h", 0)
        volume_ratio = row.get("volume_ratio", 1)
        if returns_1h < -0.015 and volume_ratio > 1.5:
            signals.append(("long", 0.8))
    
    # Long Liquidation Bounce
    elif strategy_id == "long_liquidation_bounce":
        returns_1h = row.get("returns_1h", 0)
        volume_ratio = row.get("volume_ratio", 1)
        rsi = row.get("rsi_14", 50)
        if returns_1h < -0.02 and rsi < 25 and volume_ratio > 2.0:
            signals.append(("long", 0.85))
    
    # Volume Climax Fade
    elif strategy_id == "volume_climax_fade":
        volume_ratio = row.get("volume_ratio", 1)
        wick_ratio = row.get("wick_ratio", 0)
        returns_1h = row.get("returns_1h", 0)
        if volume_ratio > 2.0 and wick_ratio > 0.3 and returns_1h > 0.003:
            signals.append(("short", 0.75))
    
    # Weak Bounce Short
    elif strategy_id == "weak_bounce_short":
        if len(prev_rows) >= 48:
            returns_4h = row.get("returns_4h", 0)
            returns_1h = row.get("returns_1h", 0)
            volume_ratio = row.get("volume_ratio", 1)
            if returns_4h < -0.02 and 0.003 < returns_1h < 0.015 and volume_ratio > 1.5:
                signals.append(("short", 0.7))
    
    # Fake Breakout Trap
    elif strategy_id == "fake_breakout_trap":
        if len(prev_rows) >= 24:
            rolling_high = prev_rows.iloc[-24:]["high"].max()
            volume_ratio = row.get("volume_ratio", 1)
            if row["high"] > rolling_high * 1.005 and volume_ratio < 1.2:
                signals.append(("short", 0.7))
    
    # Short Squeeze Hunt
    elif strategy_id == "short_squeeze_hunt":
        funding_rate = row.get("funding_rate", 0)
        oi_change_1h = row.get("oi_change_1h", 0)
        returns_1h = row.get("returns_1h", 0)
        if funding_rate < -0.00005 and oi_change_1h > 0.01 and returns_1h > 0.008:
            signals.append(("long", 0.7))
    
    # Funding Reset
    elif strategy_id == "funding_reset":
        funding_rate = row.get("funding_rate", 0)
        funding_delta = row.get("funding_delta", 0)
        if funding_rate > 0.0003 and funding_delta < -0.00005:
            signals.append(("short", 0.65))
    
    # OI Flush
    elif strategy_id == "oi_flush":
        oi_change_1h = row.get("oi_change_1h", 0)
        returns_1h = row.get("returns_1h", 0)
        if oi_change_1h < -0.05 and abs(returns_1h) < 0.02:
            signals.append(("short", 0.6))
    
    # Playbook策略（放宽条件）
    elif strategy_id == "pb_panic_reversal":
        returns_1h = row.get("returns_1h", 0)
        volume_ratio = row.get("volume_ratio", 1)
        if returns_1h < -0.015 and volume_ratio > 1.3:
            signals.append(("long", 0.7))
    
    elif strategy_id == "pb_fake_breakout":
        if len(prev_rows) >= 60:
            rolling_high = prev_rows.iloc[-60:]["high"].max()
            if row["high"] > rolling_high * 1.005:
                signals.append(("short", 0.6))
    
    elif strategy_id == "pb_oi_flush":
        funding_rate = row.get("funding_rate", 0)
        volume_ratio = row.get("volume_ratio", 1)
        if len(prev_rows) >= 1:
            returns_5m = row["close"] / prev_rows.iloc[-1]["close"] - 1
            if funding_rate > 0.0002 and volume_ratio > 1.5 and returns_5m > 0.01:
                signals.append(("long", 0.6))
    
    elif strategy_id == "pb_short_squeeze":
        funding_rate = row.get("funding_rate", 0)
        volume_ratio = row.get("volume_ratio", 1)
        if len(prev_rows) >= 1:
            returns_5m = row["close"] / prev_rows.iloc[-1]["close"] - 1
            if funding_rate > 0.0003 and returns_5m > 0.01 and volume_ratio > 1.5:
                signals.append(("long", 0.65))
    
    elif strategy_id == "pb_volume_climax":
        volume_ratio = row.get("volume_ratio", 1)
        wick_ratio = row.get("wick_ratio", 0)
        if volume_ratio > 1.8 and wick_ratio > 0.015:
            signals.append(("long", 0.55))
    
    return signals

class Position:
    def __init__(self, strategy_id, symbol, direction, entry_price, entry_time, margin):
        self.strategy_id = strategy_id
        self.symbol = symbol
        self.direction = direction  # "long" or "short"
        self.entry_price = entry_price
        self.entry_time = entry_time
        self.margin = margin
        self.highest_price = entry_price
        self.lowest_price = entry_price
        self.stop_loss_price = self._calculate_sl(entry_price)
        self.trailing_stop_price = self.stop_loss_price
        self.take_profit_price = self._calculate_tp(entry_price)
    
    def _calculate_sl(self, price):
        sl_pct = MAX_CAPITAL_SL / LEVERAGE
        if self.direction == "long":
            return price * (1 - sl_pct)
        else:
            return price * (1 + sl_pct)
    
    def _calculate_tp(self, price):
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
        
        # 固定止损
        if self.direction == "long":
            if row["low"] <= self.stop_loss_price:
                close_reason = "stop_loss"
                exit_price = self.stop_loss_price
        else:
            if row["high"] >= self.stop_loss_price:
                close_reason = "stop_loss"
                exit_price = self.stop_loss_price
        
        # 固定止盈
        if not close_reason and self.take_profit_price:
            if self.direction == "long":
                if row["high"] >= self.take_profit_price:
                    close_reason = "take_profit"
                    exit_price = self.take_profit_price
            else:
                if row["low"] <= self.take_profit_price:
                    close_reason = "take_profit"
                    exit_price = self.take_profit_price
        
        # 移动止损
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

def run_backtest(symbol, df):
    """运行单个交易对的回测"""
    print(f"\n{'='*120}")
    print(f"📊 回测 {symbol}")
    print(f"{'='*120}")
    print(f"   数据范围: {df['timestamp'].min().date()} ~ {df['timestamp'].max().date()}")
    print(f"   数据点数: {len(df):,}")
    
    positions = {}  # strategy_id -> Position
    strategy_capitals = {s: INITIAL_CAPITAL for s in STRATEGIES.keys()}
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
                    strategy_id=strategy_id,
                    symbol=symbol,
                    direction=direction,
                    entry_price=row["close"],
                    entry_time=current_time,
                    margin=margin,
                )
    
    # 强制平仓剩余持仓
    for strategy_id, pos in list(positions.items()):
        exit_price = df.iloc[-1]["close"]
        pnl = pos.calculate_pnl(exit_price)
        duration = (df.iloc[-1]["timestamp"] - pos.entry_time).total_seconds() / 3600
        
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
            "duration_hours": duration,
        }
        
        all_trades.append(trade)
        strategy_trades[strategy_id].append(trade)
        strategy_capitals[strategy_id] += pnl
    
    # 计算策略结果
    symbol_results = {}
    for strategy_id in STRATEGIES.keys():
        trades = strategy_trades[strategy_id]
        final_capital = strategy_capitals[strategy_id]
        
        if trades:
            wins = [t for t in trades if t["pnl"] > 0]
            total_return = final_capital - INITIAL_CAPITAL
            return_pct = (total_return / INITIAL_CAPITAL) * 100
            win_rate = len(wins) / len(trades) if trades else 0
            avg_win = np.mean([t["pnl"] for t in wins]) if wins else 0
            avg_loss = np.mean([t["pnl"] for t in trades if t["pnl"] <= 0]) if [t for t in trades if t["pnl"] <= 0] else 0
            
            symbol_results[strategy_id] = {
                "final_capital": final_capital,
                "total_return": total_return,
                "return_pct": return_pct,
                "total_trades": len(trades),
                "winning_trades": len(wins),
                "win_rate": win_rate * 100,
                "avg_win": avg_win,
                "avg_loss": avg_loss,
                "trades": trades,
            }
        else:
            symbol_results[strategy_id] = {
                "final_capital": INITIAL_CAPITAL,
                "total_return": 0,
                "return_pct": 0,
                "total_trades": 0,
                "winning_trades": 0,
                "win_rate": 0,
                "avg_win": 0,
                "avg_loss": 0,
                "trades": [],
            }
    
    return {
        "symbol": symbol,
        "results": symbol_results,
        "all_trades": all_trades,
    }

# 运行所有交易对
all_results = {}
all_trades = []

print(f"\n🚀 开始回测...")
print(f"{'='*120}")

for symbol in SYMBOLS:
    print(f"\n⏳ 加载 {symbol} 数据...")
    df = generate_mock_data(symbol)
    result = run_backtest(symbol, df)
    all_results[symbol] = result
    all_trades.extend(result["all_trades"])

# 汇总结果
print(f"\n{'='*120}")
print(f"📊 回测结果汇总")
print(f"{'='*120}")

# 按策略汇总
strategy_summary = defaultdict(lambda: {
    "total_return": 0,
    "total_trades": 0,
    "winning_trades": 0,
    "symbols": set(),
})

for symbol, result in all_results.items():
    for strategy_id, strat_result in result["results"].items():
        s = strategy_summary[strategy_id]
        s["total_return"] += strat_result["total_return"]
        s["total_trades"] += strat_result["total_trades"]
        s["winning_trades"] += strat_result["winning_trades"]
        s["symbols"].add(symbol)

# 打印策略排名
print(f"\n🏆 策略排名 (按总收益):")
print(f"{'='*120}")
print(f"{'策略':<30} {'交易对':<10} {'交易数':<8} {'胜率':<8} {'总收益':<15} {'年化':<10}")
print(f"{'-'*120}")

ranked_strategies = sorted(strategy_summary.items(), key=lambda x: x[1]["total_return"], reverse=True)

for strategy_id, summary in ranked_strategies:
    if summary["total_trades"] == 0:
        continue
    
    win_rate = summary["winning_trades"] / summary["total_trades"] * 100
    total_return = summary["total_return"]
    annualized = total_return / 5 * 100 / INITIAL_CAPITAL  # 假设5个月数据
    
    status = "✅" if total_return > 0 else "❌"
    print(f"{status} {STRATEGIES[strategy_id]['name']:<28} {len(summary['symbols']):<10} "
          f"{summary['total_trades']:<8} {win_rate:>6.1f}% "
          f"${total_return:>12,.2f} {annualized:>7.1f}%")

# 打印每个交易对的最佳策略
print(f"\n📈 各交易对最佳策略:")
print(f"{'='*120}")

for symbol in SYMBOLS:
    result = all_results[symbol]
    best_strat = max(
        result["results"].items(),
        key=lambda x: x[1]["total_return"]
    )
    strat_id, strat_result = best_strat
    print(f"   {symbol:10} {STRATEGIES[strat_id]['name']:30} "
          f"收益: ${strat_result['total_return']:>10,.2f} "
          f"({strat_result['return_pct']:>5.1f}%)")

# 保存结果
output_dir = backend_path / "data_lake" / "research"
output_dir.mkdir(parents=True, exist_ok=True)

output_data = {
    "config": {
        "initial_capital": INITIAL_CAPITAL,
        "leverage": LEVERAGE,
        "max_capital_sl": MAX_CAPITAL_SL,
        "trailing_stop": TRAILING_STOP,
        "fixed_tp": FIXED_TP,
    },
    "symbols": SYMBOLS,
    "strategies": STRATEGIES,
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

print(f"\n💾 结果已保存到: {output_path}")
print(f"\n{'='*120}")
print("✅ 回测完成!")
print(f"{'='*120}")
