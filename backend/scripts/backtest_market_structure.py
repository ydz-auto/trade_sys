#!/usr/bin/env python3
"""
市场结构策略 - 基于 Market Structure Features 的高级策略

这个比 RSI/MACD 更高级，因为：
1. 描述市场行为模式
2. 包含上下文信息
3. 支持事件分析
"""

from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime
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
    features: Optional[Dict] = None


@dataclass
class BacktestConfig:
    initial_capital: float = 100000.0
    commission: float = 0.0005
    slippage: float = 0.0002
    position_size: float = 0.3
    stop_loss: float = 0.02
    take_profit: float = 0.04


def market_structure_strategy(bar: Bar, position: Optional[Dict]) -> SignalType:
    """
    市场结构策略 - 结合多个市场结构特征
    
    买入条件：
    - 接近支撑位（dist_to_support_24h < 2%）
    - 突破阻力位
    - 不是Panic Dump状态
    - 趋势衰竭（可能是反弹点）
    
    卖出条件：
    - 接近阻力位
    - Trend Exhaustion
    - Panic Dump
    """
    if not bar.features:
        return SignalType.HOLD
    
    f = bar.features
    
    # ========== 市场状态检查 ==========
    
    # Panic Dump - 不买入
    if f.get("state_panic_dump", 0) == 1:
        if position:
            return SignalType.SELL
        return SignalType.HOLD
    
    # ========== 买入信号 ==========
    
    if not position:
        buy_conditions = 0
        
        # 条件1: 接近支撑位（价格在底部20%区域）
        dist_support = f.get("dist_to_support_24h", 1)
        if dist_support < 0.03:  # 距离支撑位3%以内
            buy_conditions += 1
        
        # 条件2: 位置在区间底部
        position_in_range = f.get("position_in_range_24h", 0.5)
        if position_in_range < 0.3:  # 在区间底部30%
            buy_conditions += 1
        
        # 条件3: 突破阻力位
        breakout = f.get("breakout_high_24h", False)
        if breakout:
            buy_conditions += 1
        
        # 条件4: 趋势衰竭后反弹（RSI超卖 + 回调）
        rsi = f.get("rsi_14", 50)
        if rsi < 35:
            buy_conditions += 1
        
        # 条件5: Squeeze状态（可能蓄力）
        squeeze = f.get("state_squeeze", 0)
        if squeeze == 1:
            buy_conditions += 1
        
        # 满足2个以上条件买入
        if buy_conditions >= 2:
            return SignalType.BUY
        
        return SignalType.HOLD
    
    # ========== 卖出信号 ==========
    
    # 条件1: 接近阻力位
    dist_resistance = f.get("dist_to_resistance_24h", 0)
    if dist_resistance > -0.02:  # 价格在阻力位附近
        return SignalType.SELL
    
    # 条件2: 位置在区间顶部
    position_in_range = f.get("position_in_range_24h", 0.5)
    if position_in_range > 0.8:  # 在区间顶部20%
        return SignalType.SELL
    
    # 条件3: Trend Exhaustion
    exhaustion = f.get("trend_exhaustion", 0)
    if exhaustion == 1:
        return SignalType.SELL
    
    # 条件4: Breakout失败（假突破）
    if f.get("breakout_low_24h", False):
        return SignalType.SELL
    
    # 条件5: RSI超买
    rsi = f.get("rsi_14", 50)
    if rsi > 75:
        return SignalType.SELL
    
    return SignalType.HOLD


def breakout_strategy(bar: Bar, position: Optional[Dict]) -> SignalType:
    """
    突破策略 - 简单的市场结构策略
    
    买入：突破24小时高点 + volume放大
    卖出：回到区间内
    """
    if not bar.features:
        return SignalType.HOLD
    
    f = bar.features
    
    if not position:
        # 买入条件
        breakout = f.get("breakout_high_24h", False)
        volume_ratio = f.get("volume_ratio", 1)
        
        if breakout and volume_ratio > 1.5:
            return SignalType.BUY
        
        return SignalType.HOLD
    
    # 卖出条件
    position_in_range = f.get("position_in_range_24h", 0.5)
    if position_in_range < 0.3:  # 回到区间底部
        return SignalType.SELL
    
    return SignalType.HOLD


def mean_reversion_strategy(bar: Bar, position: Optional[Dict]) -> SignalType:
    """
    均值回归策略 - 基于区间位置
    
    买入：在区间底部 + RSI超卖
    卖出：在区间中部以上
    """
    if not bar.features:
        return SignalType.HOLD
    
    f = bar.features
    position_in_range = f.get("position_in_range_24h", 0.5)
    rsi = f.get("rsi_14", 50)
    
    if not position:
        # 买入条件
        if position_in_range < 0.2 and rsi < 35:
            return SignalType.BUY
        
        return SignalType.HOLD
    
    # 卖出条件
    if position_in_range > 0.6:
        return SignalType.SELL
    
    return SignalType.HOLD


class SimpleBacktest:
    """简化回测"""
    
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
            self.bars.append(Bar(
                timestamp=row["timestamp"],
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
                features=row.to_dict()
            ))
    
    def run(self, strategy):
        self.trades = []
        self.equity_curve = []
        self.position = None
        self.capital = self.config.initial_capital
        peak = self.capital
        
        for bar in self.bars:
            signal = strategy(bar, self.position)
            
            if self.position:
                pnl_pct = (bar.close - self.position["entry_price"]) / self.position["entry_price"]
                
                # 止损
                if pnl_pct <= -self.config.stop_loss:
                    self._close(bar, "sl")
                # 止盈
                elif pnl_pct >= self.config.take_profit:
                    self._close(bar, "tp")
                # 信号卖出
                elif signal == SignalType.SELL:
                    self._close(bar, "signal")
            
            if not self.position and signal == SignalType.BUY:
                self._open(bar)
            
            # 计算权益
            equity = self.capital
            if self.position:
                pos_pnl = (bar.close - self.position["entry_price"]) * self.position["qty"]
                equity += pos_pnl
            
            self.equity_curve.append(equity)
            if equity > peak:
                peak = equity
        
        if self.position:
            self._close(self.bars[-1], "end")
        
        return self._metrics()
    
    def _open(self, bar):
        value = self.capital * self.config.position_size
        qty = value / bar.close
        cost = value * (1 + self.config.commission)
        
        self.position = {
            "entry_price": bar.close,
            "qty": qty,
            "capital": cost
        }
        self.capital -= cost
    
    def _close(self, bar, reason):
        if not self.position:
            return
        
        pnl = (bar.close - self.position["entry_price"]) * self.position["qty"]
        pnl -= self.position["capital"] * self.config.commission
        
        self.trades.append({
            "entry": self.position["entry_price"],
            "exit": bar.close,
            "pnl": pnl,
            "reason": reason
        })
        
        self.capital += self.position["capital"] + pnl
        self.position = None
    
    def _metrics(self):
        total = self.equity_curve[-1] - self.config.initial_capital
        total_pct = total / self.config.initial_capital
        
        # 最大回撤
        peak = self.config.initial_capital
        max_dd = 0
        for e in self.equity_curve:
            if e > peak:
                peak = e
            dd = peak - e
            if dd > max_dd:
                max_dd = dd
        max_dd_pct = max_dd / peak if peak > 0 else 0
        
        # 交易统计
        wins = [t for t in self.trades if t["pnl"] > 0]
        losses = [t for t in self.trades if t["pnl"] <= 0]
        win_rate = len(wins) / len(self.trades) if self.trades else 0
        
        total_wins = sum(t["pnl"] for t in wins)
        total_losses = abs(sum(t["pnl"] for t in losses))
        pf = total_wins / total_losses if total_losses > 0 else 0
        
        return {
            "return": total,
            "return_pct": total_pct,
            "max_dd_pct": max_dd_pct,
            "total_trades": len(self.trades),
            "win_rate": win_rate,
            "profit_factor": pf
        }


def main():
    print("="*70)
    print("📊 市场结构策略回测")
    print("="*70)
    
    # 加载数据
    data_path = Path("data_lake/features/binance/BTCUSDT/features_with_structure.parquet")
    df = pd.read_parquet(data_path)
    
    # 重采样到小时级别
    df_hourly = df.set_index("timestamp").resample("1h").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
        "rsi_14": "last",
        "dist_to_resistance_24h": "last",
        "dist_to_support_24h": "last",
        "position_in_range_24h": "last",
        "breakout_high_24h": "max",
        "breakout_low_24h": "max",
        "state_panic_dump": "max",
        "state_squeeze": "max",
        "trend_exhaustion": "max",
        "volume_ratio": "last"
    }).dropna().reset_index()
    
    # 取2024全年
    df_2024 = df_hourly[df_hourly["timestamp"].dt.year == 2024].copy()
    
    print(f"\n📊 数据: {len(df_2024)} 小时K线 (2024全年)")
    
    config = BacktestConfig(
        initial_capital=100000,
        commission=0.0005,
        slippage=0.0002,
        position_size=0.3,
        stop_loss=0.02,
        take_profit=0.04
    )
    
    strategies = [
        ("市场结构策略", market_structure_strategy),
        ("突破策略", breakout_strategy),
        ("均值回归策略", mean_reversion_strategy),
    ]
    
    results = []
    
    for name, strategy in strategies:
        print(f"\n{'='*70}")
        print(f"🎯 {name}")
        print("="*70)
        
        engine = SimpleBacktest(config)
        engine.load_df(df_2024)
        metrics = engine.run(strategy)
        
        print(f"\n💰 总收益: ${metrics['return']:,.2f} ({metrics['return_pct']:.2%})")
        print(f"📉 最大回撤: {metrics['max_dd_pct']:.2%}")
        print(f"🎯 胜率: {metrics['win_rate']:.2%}")
        print(f"📊 总交易: {metrics['total_trades']}")
        print(f"💰 盈亏比: {metrics['profit_factor']:.2f}")
        
        results.append((name, metrics))
    
    # 总结
    print(f"\n{'='*70}")
    print("📊 策略对比总结")
    print("="*70)
    print(f"{'策略':<25} | {'收益':>10} | {'最大回撤':>10} | {'胜率':>6} | {'交易数':>6}")
    print("-"*75)
    
    for name, m in results:
        print(f"{name:<25} | {m['return_pct']*100:>9.2f}% | {m['max_dd_pct']*100:>9.2f}% | {m['win_rate']*100:>5.1f}% | {m['total_trades']:>6}")
    
    print("\n✅ 完成！")


if __name__ == "__main__":
    main()
