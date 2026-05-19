#!/usr/bin/env python3
"""
优化策略回测 - 使用更长时间框架

功能：
- 重采样到更长时间框架
- 实现更合理的策略
- 减少交易频率
"""

from pathlib import Path
from typing import Dict, Optional, List, Any
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
    features: Optional[Dict] = None


@dataclass
class Trade:
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    pnl_pct: float
    side: SignalType


@dataclass
class PerformanceMetrics:
    total_return: float = 0.0
    total_return_pct: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0


@dataclass
class BacktestConfig:
    initial_capital: float = 100000.0
    commission: float = 0.0005  # 0.05% (Binance合约费率)
    slippage: float = 0.0002    # 0.02%
    position_size: float = 0.2  # 20%
    stop_loss: float = 0.015    # 1.5%
    take_profit: float = 0.03   # 3%


@dataclass
class BacktestResult:
    config: BacktestConfig
    metrics: PerformanceMetrics
    trades: List[Trade]
    equity_curve: List[float]
    drawdown_curve: List[float]
    start_date: datetime
    end_date: datetime


class BacktestEngine:
    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()
        self._bars: List[Bar] = []
        self._trades: List[Trade] = []
        self._equity_curve: List[float] = []
        self._drawdown_curve: List[float] = []
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

    def run(self, signal_generator) -> BacktestResult:
        self._trades = []
        self._equity_curve = []
        self._drawdown_curve = []
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
            drawdown_pct = (peak_equity - current_equity) / peak_equity if peak_equity > 0 else 0
            self._drawdown_curve.append(drawdown_pct)

        if self._position:
            self._close_position(self._bars[-1], "end")

        metrics = self._calculate_metrics()
        return BacktestResult(
            config=self.config,
            metrics=metrics,
            trades=self._trades,
            equity_curve=self._equity_curve,
            drawdown_curve=self._drawdown_curve,
            start_date=self._bars[0].timestamp,
            end_date=self._bars[-1].timestamp
        )

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
        trade = Trade(
            entry_time=self._position["entry_time"],
            exit_time=bar.timestamp,
            entry_price=self._position["entry_price"],
            exit_price=exit_price,
            quantity=self._position["quantity"],
            pnl=pnl,
            pnl_pct=pnl / self._position["capital_used"],
            side=self._position["side"]
        )
        self._trades.append(trade)
        self._capital += self._position["capital_used"] + pnl
        self._position = None

    def _calculate_metrics(self) -> PerformanceMetrics:
        total_return = self._equity_curve[-1] - self.config.initial_capital if self._equity_curve else 0
        total_return_pct = total_return / self.config.initial_capital if self.config.initial_capital > 0 else 0

        peak = self.config.initial_capital
        max_drawdown = 0.0
        for equity in self._equity_curve:
            if equity > peak:
                peak = equity
            drawdown = peak - equity
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        max_drawdown_pct = max_drawdown / peak if peak > 0 else 0

        total_trades = len(self._trades)
        winning_trades = sum(1 for t in self._trades if t.pnl > 0)
        losing_trades = sum(1 for t in self._trades if t.pnl <= 0)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0

        avg_win = sum(t.pnl for t in self._trades if t.pnl > 0) / winning_trades if winning_trades > 0 else 0
        avg_loss = sum(t.pnl for t in self._trades if t.pnl <= 0) / losing_trades if losing_trades > 0 else 0

        total_wins = sum(t.pnl for t in self._trades if t.pnl > 0)
        total_losses = abs(sum(t.pnl for t in self._trades if t.pnl <= 0))
        profit_factor = total_wins / total_losses if total_losses > 0 else 0

        if len(self._equity_curve) > 1:
            returns = []
            for i in range(1, len(self._equity_curve)):
                ret = (self._equity_curve[i] - self._equity_curve[i-1]) / self._equity_curve[i-1]
                returns.append(ret)
            avg_return = sum(returns) / len(returns) if returns else 0
            std_return = (sum((r - avg_return)**2 for r in returns) / len(returns))**0.5 if returns else 0
            sharpe_ratio = avg_return / std_return * (365**0.5) if std_return > 0 else 0
        else:
            sharpe_ratio = 0

        return PerformanceMetrics(
            total_return=total_return,
            total_return_pct=total_return_pct,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_drawdown_pct,
            win_rate=win_rate,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor
        )


def resample_df(df: pd.DataFrame, freq: str = "1H") -> pd.DataFrame:
    """重采样DataFrame到更长时间框架"""
    df_resampled = df.set_index("timestamp").resample(freq).agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
        "rsi_14": "last",
        "macd": "last",
        "macd_signal": "last",
        "funding_rate": "last",
        "open_interest": "last"
    }).dropna().reset_index()
    return df_resampled


class ImprovedStrategy:
    """优化策略 - 多时间框架+Funding+OI"""
    def __init__(self):
        self.rsi_overbought = 70
        self.rsi_oversold = 30
        self.min_funding = -0.0001

    def __call__(self, bar: Bar, position: Optional[Dict]) -> SignalType:
        if not bar.features:
            return SignalType.HOLD

        rsi = bar.features.get("rsi_14")
        macd = bar.features.get("macd")
        macd_signal = bar.features.get("macd_signal")
        funding = bar.features.get("funding_rate")

        if position:
            # 持仓
            if rsi and rsi > 65:
                return SignalType.SELL
            if macd and macd_signal and macd < macd_signal - 5:
                return SignalType.SELL
            return SignalType.HOLD

        # 空仓
        buy_condition = False

        # RSI超卖
        if rsi and rsi < 35:
            buy_condition = True

        # MACD上穿
        if macd and macd_signal and macd > macd_signal:
            buy_condition = True

        # Funding负（对多头有利）
        if funding and funding < -0.0001:
            buy_condition = True

        if buy_condition:
            return SignalType.BUY

        return SignalType.HOLD


def simple_rsi_strategy(bar: Bar, position: Optional[Dict]) -> SignalType:
    """简化RSI策略"""
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


def main():
    print("="*70)
    print("📊 优化策略回测")
    print("="*70)

    data_path = Path("data_lake/features/binance/BTCUSDT/features.parquet")
    df = pd.read_parquet(data_path)
    print(f"原始数据: {len(df)} 条 (1分钟级别)")

    # 重采样到1小时
    df_hourly = resample_df(df, "1H")
    print(f"重采样后: {len(df_hourly)} 条 (1小时级别)")

    # 回测区间
    mask = (df_hourly['timestamp'] >= '2024-01-01') & (df_hourly['timestamp'] < '2025-01-01')
    df_backtest = df_hourly.loc[mask].copy()
    print(f"回测样本: {len(df_backtest)} 条 (2024全年)")

    config = BacktestConfig(
        initial_capital=100000,
        commission=0.0005,
        slippage=0.0002,
        position_size=0.2,
        stop_loss=0.015,
        take_profit=0.03
    )

    # 回测策略
    print(f"\n{'='*70}")
    print("🎯 优化策略 (小时级别, RSI+MACD+Funding)")
    print("="*70)
    engine = BacktestEngine(config)
    engine.load_df(df_backtest)
    result = engine.run(ImprovedStrategy())
    print_result(result)

    print(f"\n{'='*70}")
    print("🎯 简化RSI策略 (小时级别)")
    print("="*70)
    engine = BacktestEngine(config)
    engine.load_df(df_backtest)
    result_simple = engine.run(simple_rsi_strategy)
    print_result(result_simple)

    print(f"\n{'='*70}")
    print("📊 对比总结")
    print("="*70)
    print(f"{'策略':<25} | {'收益':>10} | {'夏普':>6} | {'最大回撤':>10} | {'胜率':>6} | {'交易数':>6}")
    print("-"*75)
    m1 = result.metrics
    m2 = result_simple.metrics
    print(f"{'优化策略':<25} | {m1.total_return_pct*100:>9.2f}% | {m1.sharpe_ratio:>6.2f} | {m1.max_drawdown_pct*100:>9.2f}% | {m1.win_rate*100:>5.1f}% | {m1.total_trades:>6}")
    print(f"{'简化RSI策略':<25} | {m2.total_return_pct*100:>9.2f}% | {m2.sharpe_ratio:>6.2f} | {m2.max_drawdown_pct*100:>9.2f}% | {m2.win_rate*100:>5.1f}% | {m2.total_trades:>6}")

    print("\n" + "="*70)
    print("✅ 回测完成！")
    print("="*70)


def print_result(result: BacktestResult):
    m = result.metrics
    print(f"\n💰 总收益: ${m.total_return:,.2f} ({m.total_return_pct:.2%})")
    print(f"📈 夏普比率: {m.sharpe_ratio:.2f}")
    print(f"📉 最大回撤: {m.max_drawdown_pct:.2%}")
    print(f"🎯 胜率: {m.win_rate:.2%}")
    print(f"📊 总交易: {m.total_trades}")
    print(f"💰 盈亏比: {m.profit_factor:.2f}")
    if m.total_trades > 0:
        print(f"✅ 盈利: {m.winning_trades} | ❌ 亏损: {m.losing_trades}")
        print(f"📊 平均盈利: ${m.avg_win:,.2f} | 平均亏损: ${m.avg_loss:,.2f}")


if __name__ == "__main__":
    main()
