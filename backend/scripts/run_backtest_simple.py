#!/usr/bin/env python3
"""
简单回测 - 用2024年数据，小时级别
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
class Trade:
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    pnl: float
    side: SignalType


@dataclass
class PerformanceMetrics:
    total_return: float = 0.0
    total_return_pct: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    profit_factor: float = 0.0


@dataclass
class BacktestConfig:
    initial_capital: float = 100000.0
    commission: float = 0.0005
    slippage: float = 0.0002
    position_size: float = 0.2
    stop_loss: float = 0.015
    take_profit: float = 0.03


class BacktestEngine:
    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()
        self._bars: List[Bar] = []
        self._trades: List[Trade] = []
        self._equity_curve: List[float] = []
        self._position: Optional[Dict] = None
        self._capital: float = 0.0

    def load_df(self, df: pd.DataFrame) -> "BacktestEngine":
        self._bars = []
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
            self._bars.append(bar)
        return self

    def run(self, signal_generator):
        self._trades = []
        self._equity_curve = []
        self._position = None
        self._capital = self.config.initial_capital
        peak_equity = self._capital

        for bar in self._bars:
            signal = signal_generator(bar, self._position)

            if self._position:
                pnl_pct = (bar.close - self._position["entry_price"]) / self._position["entry_price"]
                if self._position["side"] == SignalType.SELL:
                    pnl_pct = -pnl_pct

                if pnl_pct <= -self.config.stop_loss:
                    self._close_position(bar, "stop_loss")
                elif pnl_pct >= self.config.take_profit:
                    self._close_position(bar, "take_profit")
                elif signal == SignalType.SELL:
                    self._close_position(bar, "signal")

            if not self._position and signal != SignalType.HOLD:
                self._open_position(bar, signal)

            current_equity = self._capital
            if self._position:
                pos_pnl = (bar.close - self._position["entry_price"]) * self._position["quantity"]
                if self._position["side"] == SignalType.SELL:
                    pos_pnl = -pos_pnl
                current_equity += pos_pnl

            self._equity_curve.append(current_equity)

            if current_equity > peak_equity:
                peak_equity = current_equity

        if self._position:
            self._close_position(self._bars[-1], "end")

        return self._calculate_metrics()

    def _open_position(self, bar: Bar, signal: SignalType):
        position_value = self._capital * self.config.position_size
        quantity = position_value / bar.close
        cost = position_value * (1 + self.config.commission + self.config.slippage)
        if cost > self._capital:
            return
        self._position = {
            "entry_time": bar.timestamp,
            "entry_price": bar.close * (1 + self.config.slippage),
            "quantity": quantity,
            "side": signal,
            "capital_used": cost
        }
        self._capital -= cost

    def _close_position(self, bar: Bar, reason: str):
        if not self._position:
            return
        exit_price = bar.close * (1 - self.config.slippage)
        if self._position["side"] == SignalType.SELL:
            exit_price = bar.close * (1 + self.config.slippage)
        pnl = (exit_price - self._position["entry_price"]) * self._position["quantity"]
        if self._position["side"] == SignalType.SELL:
            pnl = -pnl
        pnl -= self._position["capital_used"] * self.config.commission
        self._trades.append(Trade(
            entry_time=self._position["entry_time"],
            exit_time=bar.timestamp,
            entry_price=self._position["entry_price"],
            exit_price=exit_price,
            pnl=pnl,
            side=self._position["side"]
        ))
        self._capital += self._position["capital_used"] + pnl
        self._position = None

    def _calculate_metrics(self) -> PerformanceMetrics:
        total_return = self._equity_curve[-1] - self.config.initial_capital if self._equity_curve else 0
        total_return_pct = total_return / self.config.initial_capital

        peak = self.config.initial_capital
        max_dd_pct = 0.0
        for equity in self._equity_curve:
            if equity > peak:
                peak = equity
            dd_pct = (peak - equity) / peak
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct

        total_trades = len(self._trades)
        winning = sum(1 for t in self._trades if t.pnl > 0)
        win_rate = winning / total_trades if total_trades > 0 else 0

        total_wins = sum(t.pnl for t in self._trades if t.pnl > 0)
        total_losses = abs(sum(t.pnl for t in self._trades if t.pnl <= 0))
        profit_factor = total_wins / total_losses if total_losses > 0 else 0

        if len(self._equity_curve) > 1:
            returns = [
                (self._equity_curve[i] - self._equity_curve[i-1]) / self._equity_curve[i-1]
                for i in range(1, len(self._equity_curve))
            ]
            avg = sum(returns) / len(returns)
            std = (sum((r - avg)**2 for r in returns) / len(returns))**0.5
            sharpe = avg / std * (365**0.5) if std > 0 else 0
        else:
            sharpe = 0

        return PerformanceMetrics(
            total_return=total_return,
            total_return_pct=total_return_pct,
            sharpe_ratio=sharpe,
            max_drawdown_pct=max_dd_pct,
            win_rate=win_rate,
            total_trades=total_trades,
            profit_factor=profit_factor
        )


def rsi_strategy(bar: Bar, position: Optional[Dict]) -> SignalType:
    if not bar.features:
        return SignalType.HOLD

    rsi = bar.features.get("rsi_14")
    if not rsi:
        return SignalType.HOLD

    if position:
        if rsi > 65:
            return SignalType.SELL
        return SignalType.HOLD

    if rsi < 35:
        return SignalType.BUY

    return SignalType.HOLD


def buy_and_hold(bar: Bar, position: Optional[Dict]) -> SignalType:
    """买入持有策略（基准）"""
    if not position:
        return SignalType.BUY
    return SignalType.HOLD


def main():
    print("="*70)
    print("📊 策略回测 - BTC 2024全年")
    print("="*70)

    data_path = Path("data_lake/features/binance/BTCUSDT/features.parquet")
    df = pd.read_parquet(data_path)

    # 取2024全年数据，重采样到小时级别
    df_2024 = df[df["timestamp"].dt.year == 2024].copy()
    df_2024 = df_2024.set_index("timestamp").resample("1h").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
        "rsi_14": "last",
        "funding_rate": "last"
    }).dropna().reset_index()

    print(f"\n📊 回测数据: {len(df_2024)} 根K线 (2024全年, 小时级别)")
    print(f"   价格范围: ${df_2024['low'].min():,.0f} ~ ${df_2024['high'].max():,.0f}")

    config = BacktestConfig(
        initial_capital=100000,
        commission=0.0005,
        slippage=0.0002,
        position_size=0.2,
        stop_loss=0.015,
        take_profit=0.03
    )

    # 基准策略：买入持有
    print(f"\n{'='*70}")
    print("📈 基准策略: 买入持有")
    print("="*70)
    engine = BacktestEngine(config)
    engine.load_df(df_2024)
    m1 = engine.run(buy_and_hold)
    print_result(m1, engine._trades)

    # RSI策略
    print(f"\n{'='*70}")
    print("🎯 RSI策略: RSI<35买入, RSI>65卖出")
    print("="*70)
    engine = BacktestEngine(config)
    engine.load_df(df_2024)
    m2 = engine.run(rsi_strategy)
    print_result(m2, engine._trades)

    print(f"\n{'='*70}")
    print("📊 总结对比")
    print("="*70)
    print(f"{'策略':<20} | {'收益':>10} | {'夏普':>6} | {'最大回撤':>10} | {'胜率':>6} | {'交易数':>6}")
    print("-"*75)
    print(f"{'买入持有':<20} | {m1.total_return_pct*100:>9.2f}% | {m1.sharpe_ratio:>6.2f} | {m1.max_drawdown_pct*100:>9.2f}% | {'-':>6} | {m1.total_trades:>6}")
    print(f"{'RSI策略':<20} | {m2.total_return_pct*100:>9.2f}% | {m2.sharpe_ratio:>6.2f} | {m2.max_drawdown_pct*100:>9.2f}% | {m2.win_rate*100:>5.1f}% | {m2.total_trades:>6}")

    print("\n✅ 完成！")


def print_result(metrics: PerformanceMetrics, trades: List[Trade]):
    print(f"\n💰 总收益: ${metrics.total_return:,.2f} ({metrics.total_return_pct:.2%})")
    print(f"📈 夏普比率: {metrics.sharpe_ratio:.2f}")
    print(f"📉 最大回撤: {metrics.max_drawdown_pct:.2%}")
    print(f"🎯 胜率: {metrics.win_rate:.2%}")
    print(f"📊 总交易: {metrics.total_trades}")
    print(f"💰 盈亏比: {metrics.profit_factor:.2f}")


if __name__ == "__main__":
    main()
