#!/usr/bin/env python3
"""
Crypto Behavioral Playbooks 回测

基于历史研究结果实现的策略回测：

研究结果摘要（2024年）：
┌─────────────────────────┬────────┬──────────┬──────────────┬────────────────┐
│ Playbook               │ 样本数 │ 1h收益   │ 正收益概率   │ 最佳入场/出场  │
├─────────────────────────┼────────┼──────────┼──────────────┼────────────────┤
│ Panic Reversal         │  1855  │  +0.20%  │    61.5%     │ immediate/1h   │
│ Volume Climax          │   145  │  +0.36%  │    64.1%     │ immediate/1h   │
│ Weekend Manipulation    │   135  │  +0.31%  │    60.7%     │ immediate/1h   │
│ OI Flush               │   124  │  +0.13%  │    60.5%     │ immediate/1h   │
│ Fake Breakout (反向)   │    38  │  -0.68%  │    73.7%*    │ immediate/1h   │
│ Short Squeeze (反向)   │    20  │  -1.75%  │    70.0%*    │ wait_15m/15m   │
└─────────────────────────┴────────┴──────────┴──────────────┴────────────────┘
* 反向胜率：做空获利的概率
"""

from pathlib import Path
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

import pandas as pd
import numpy as np


class SignalType(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class Bar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    features: Dict


@dataclass
class BacktestConfig:
    initial_capital: float = 100000.0
    commission: float = 0.0005
    slippage: float = 0.0002
    position_size: float = 0.5
    stop_loss: float = 0.01
    take_profit: float = 0.04
    max_hold_hours: int = 4


class PlaybookBacktester:
    """Playbooks 策略回测"""
    
    def __init__(self, config: BacktestConfig):
        self.config = config
        self.bars = []
        self.trades = []
        self.equity_curve = []
        self.position = None
        self.capital = 0.0
        
    def load_df(self, df: pd.DataFrame):
        self.bars = []
        for _, row in df.iterrows():
            bar = Bar(
                timestamp=row["timestamp"],
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
                features=row.to_dict()
            )
            self.bars.append(bar)
    
    def prepare_features(self):
        """准备特征"""
        for i, bar in enumerate(self.bars):
            f = bar.features
            
            if i >= 1:
                f["return_1h"] = (bar.close - self.bars[i-1].close) / self.bars[i-1].close
            else:
                f["return_1h"] = 0
            
            intrabar_range = (bar.high - bar.low) / bar.close
            f["intrabar_volatility"] = intrabar_range
            
            avg_volume = np.mean([b.volume for b in self.bars[max(0,i-24):i+1]]) if i > 0 else bar.volume
            f["volume_ratio"] = bar.volume / avg_volume if avg_volume > 0 else 1
            
            f["hour"] = bar.timestamp.hour
            f["day_of_week"] = bar.timestamp.dayofweek
            f["is_weekend"] = bar.timestamp.dayofweek >= 5
            
            def get_session(hour):
                if 0 <= hour < 8:
                    return "asia"
                elif 8 <= hour < 16:
                    return "europe"
                else:
                    return "us"
            f["session"] = get_session(f["hour"])
    
    def detect_panic_reversal(self, bar: Bar, i: int) -> bool:
        """检测 Panic Reversal - 基于研究结果"""
        f = bar.features
        
        if i < 2:
            return False
        
        return (
            f.get("return_1h", 0) < -0.02 and
            f.get("volume_ratio", 1) > 1.5
        )
    
    def detect_volume_climax(self, bar: Bar, i: int) -> bool:
        """检测 Volume Climax - 基于研究结果"""
        f = bar.features
        
        if i < 2:
            return False
        
        return (
            f.get("volume_ratio", 1) > 2.0 and
            f.get("intrabar_volatility", 0) > 0.025
        )
    
    def detect_weekend_manipulation(self, bar: Bar, i: int) -> bool:
        """检测 Weekend Manipulation - 基于研究结果"""
        f = bar.features
        
        if i < 2:
            return False
        
        return (
            f.get("is_weekend", False) and
            f.get("volume_ratio", 1) < 0.8 and
            f.get("intrabar_volatility", 0) > 0.015
        )
    
    def detect_oi_flush(self, bar: Bar, i: int) -> bool:
        """检测 OI Flush - 基于研究结果"""
        f = bar.features
        
        if i < 2:
            return False
        
        funding = f.get("funding_rate", 0)
        regime = f.get("regime", "ranging")
        
        return (
            funding > 0.0003 and
            f.get("volume_ratio", 1) > 2.0 and
            regime == "volatile"
        )
    
    def detect_fake_breakout(self, bar: Bar, i: int) -> bool:
        """检测 Fake Breakout"""
        f = bar.features
        
        if i < 2:
            return False
        
        rolling_high = max(b.high for b in self.bars[max(0,i-24):i])
        breakout = bar.high > rolling_high * 1.005
        
        if breakout and i + 1 < len(self.bars):
            future_price = self.bars[i+1].close
            fake = future_price < rolling_high
            return fake
        
        return False
    
    def detect_short_squeeze(self, bar: Bar, i: int) -> bool:
        """检测 Short Squeeze"""
        f = bar.features
        
        if i < 2:
            return False
        
        funding = f.get("funding_rate", 0)
        price_up = f.get("return_1h", 0) > 0.01
        volume_up = f.get("volume_ratio", 1) > 1.5
        
        return (
            funding > 0.0003 and
            price_up and
            volume_up
        )
    
    def playbook_strategy(self, bar: Bar, position: Optional[Dict], i: int) -> Tuple[SignalType, str]:
        """Playbooks 综合策略 - 返回 (信号, 原因)"""
        f = bar.features
        
        is_panic = self.detect_panic_reversal(bar, i)
        is_climax = self.detect_volume_climax(bar, i)
        is_weekend = self.detect_weekend_manipulation(bar, i)
        is_oi_flush = self.detect_oi_flush(bar, i)
        
        if position:
            elapsed = (bar.timestamp - position["entry_time"]).total_seconds() / 3600
            
            if elapsed >= self.config.max_hold_hours:
                return SignalType.SELL, "time_exit"
            
            if is_oi_flush or is_panic:
                return SignalType.SELL, "double_signal"
            
            pnl_pct = (bar.close - position["entry_price"]) / position["entry_price"]
            if position["type"] == "short":
                pnl_pct = -pnl_pct
            
            if pnl_pct >= self.config.take_profit:
                return SignalType.SELL, "tp"
            if pnl_pct <= -self.config.stop_loss:
                return SignalType.SELL, "sl"
            
            return SignalType.HOLD, "hold"
        
        if is_panic:
            return SignalType.BUY, "panic"
        if is_climax:
            return SignalType.BUY, "climax"
        if is_weekend:
            return SignalType.BUY, "weekend"
        if is_oi_flush:
            return SignalType.BUY, "oi_flush"
        
        return SignalType.HOLD, "none"
    
    def run(self, strategy_name: str = "Playbooks Strategy"):
        self.trades = []
        self.equity_curve = []
        self.position = None
        self.capital = self.config.initial_capital
        peak = self.capital
        
        for i, bar in enumerate(self.bars):
            signal, reason = self.playbook_strategy(bar, self.position, i)
            
            if self.position:
                pnl_pct = (bar.close - self.position["entry_price"]) / self.position["entry_price"]
                if self.position["type"] == "short":
                    pnl_pct = -pnl_pct
                
                if pnl_pct <= -self.config.stop_loss:
                    self._close(bar, "sl")
                elif pnl_pct >= self.config.take_profit:
                    self._close(bar, "tp")
                elif signal == SignalType.SELL:
                    self._close(bar, reason)
            
            if not self.position:
                if signal == SignalType.BUY:
                    self._open(bar, reason)
            
            equity = self.capital
            if self.position:
                pos_pnl = (bar.close - self.position["entry_price"]) * self.position["qty"]
                equity += pos_pnl
            
            self.equity_curve.append({
                "timestamp": bar.timestamp,
                "equity": equity,
                "position": self.position is not None
            })
            
            if equity > peak:
                peak = equity
        
        if self.position:
            self._close(self.bars[-1], "end")
        
        return self._metrics()
    
    def _open(self, bar: Bar, reason: str):
        value = self.capital * self.config.position_size
        qty = value / bar.close
        cost = value * (1 + self.config.commission)
        
        self.position = {
            "type": "long",
            "entry_price": bar.close,
            "qty": qty,
            "capital": cost,
            "entry_time": bar.timestamp,
            "reason": reason
        }
        self.capital -= cost
    
    def _open_short(self, bar: Bar, reason: str):
        value = self.capital * self.config.position_size
        qty = value / bar.close
        proceeds = value * (1 - self.config.commission)
        
        self.position = {
            "type": "short",
            "entry_price": bar.close,
            "qty": qty,
            "capital": proceeds,
            "entry_time": bar.timestamp,
            "reason": reason
        }
        self.capital += proceeds
    
    def _close(self, bar: Bar, reason: str):
        if not self.position:
            return
        
        if self.position["type"] == "long":
            pnl = (bar.close - self.position["entry_price"]) * self.position["qty"]
            pnl -= self.position["capital"] * self.config.commission
        else:
            pnl = (self.position["entry_price"] - bar.close) * self.position["qty"]
            pnl -= self.position["capital"] * self.config.commission
        
        self.trades.append({
            "type": self.position["type"],
            "entry": self.position["entry_price"],
            "exit": bar.close,
            "pnl": pnl,
            "reason": self.position["reason"],
            "close_reason": reason,
            "entry_time": self.position["entry_time"],
            "exit_time": bar.timestamp
        })
        
        self.capital += self.position["capital"] + pnl
        self.position = None
    
    def _metrics(self) -> Dict:
        total = self.equity_curve[-1]["equity"] - self.config.initial_capital
        total_pct = total / self.config.initial_capital
        
        peak = self.config.initial_capital
        max_dd = 0
        for e in self.equity_curve:
            if e["equity"] > peak:
                peak = e["equity"]
            dd = peak - e["equity"]
            if dd > max_dd:
                max_dd = dd
        max_dd_pct = max_dd / peak if peak > 0 else 0
        
        longs = [t for t in self.trades if t["type"] == "long"]
        shorts = [t for t in self.trades if t["type"] == "short"]
        
        wins = [t for t in self.trades if t["pnl"] > 0]
        losses = [t for t in self.trades if t["pnl"] <= 0]
        win_rate = len(wins) / len(self.trades) if self.trades else 0
        
        total_wins = sum(t["pnl"] for t in wins)
        total_losses = abs(sum(t["pnl"] for t in losses))
        pf = total_wins / total_losses if total_losses > 0 else 0
        
        long_wins = len([t for t in longs if t["pnl"] > 0])
        short_wins = len([t for t in shorts if t["pnl"] > 0])
        
        by_reason = {}
        for t in self.trades:
            reason = t["reason"]
            if reason not in by_reason:
                by_reason[reason] = {"count": 0, "wins": 0, "total_pnl": 0}
            by_reason[reason]["count"] += 1
            if t["pnl"] > 0:
                by_reason[reason]["wins"] += 1
            by_reason[reason]["total_pnl"] += t["pnl"]
        
        return {
            "return": total,
            "return_pct": total_pct,
            "max_dd_pct": max_dd_pct,
            "total_trades": len(self.trades),
            "long_trades": len(longs),
            "short_trades": len(shorts),
            "win_rate": win_rate,
            "long_win_rate": long_wins / len(longs) if longs else 0,
            "short_win_rate": short_wins / len(shorts) if shorts else 0,
            "profit_factor": pf,
            "by_reason": by_reason
        }


def main():
    print("="*80)
    print("📊 Crypto Behavioral Playbooks 回测")
    print("="*80)
    
    data_path = Path("data_lake/features/binance/BTCUSDT/features_with_structure.parquet")
    df = pd.read_parquet(data_path)
    
    df_hourly = df.set_index("timestamp").resample("1h").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
        "rsi_14": "last",
        "funding_rate": "last",
        "regime": "last",
    }).dropna().reset_index()
    
    df_2024 = df_hourly[df_hourly["timestamp"].dt.year == 2024].copy()
    print(f"\n📊 数据: {len(df_2024)} 小时K线 (2024全年)")
    
    config = BacktestConfig(
        initial_capital=100000,
        commission=0.0005,
        slippage=0.0002,
        position_size=0.3,
        stop_loss=0.015,
        take_profit=0.03
    )
    
    tester = PlaybookBacktester(config)
    tester.load_df(df_2024)
    tester.prepare_features()
    
    print("\n" + "="*80)
    print("🎯 Playbooks 综合策略回测")
    print("="*80)
    
    metrics = tester.run("Playbooks Strategy")
    
    print(f"\n{'='*60}")
    print("📈 总体表现")
    print("="*60)
    print(f"💰 总收益: ${metrics['return']:,.2f} ({metrics['return_pct']:.2%})")
    print(f"📉 最大回撤: {metrics['max_dd_pct']:.2%}")
    print(f"🎯 胜率: {metrics['win_rate']:.2%}")
    print(f"💰 盈亏比: {metrics['profit_factor']:.2f}")
    print(f"📊 总交易: {metrics['total_trades']}")
    print(f"   - 多头交易: {metrics['long_trades']} (胜率: {metrics['long_win_rate']:.1%})")
    print(f"   - 空头交易: {metrics['short_trades']} (胜率: {metrics['short_win_rate']:.1%})")
    
    print(f"\n{'='*60}")
    print("📋 按 Playbook 类型分析")
    print("="*60)
    print(f"{'Playbook':<20} | {'交易数':>6} | {'胜率':>6} | {'总收益':>12}")
    print("-"*60)
    
    playbook_names = {
        "panic": "Panic Reversal",
        "climax": "Volume Climax",
        "weekend": "Weekend",
        "oi_flush": "OI Flush",
        "fake": "Fake Breakout",
        "squeeze": "Short Squeeze"
    }
    
    for reason, data in sorted(metrics["by_reason"].items(), key=lambda x: -x[1]["total_pnl"]):
        name = playbook_names.get(reason, reason)
        win_rate = data["wins"] / data["count"] if data["count"] > 0 else 0
        print(f"{name:<20} | {data['count']:>6} | {win_rate:>6.1%} | ${data['total_pnl']:>10,.2f}")
    
    print(f"\n{'='*80}")
    print("✅ 回测完成！")
    print("="*80)
    
    return metrics


if __name__ == "__main__":
    main()
