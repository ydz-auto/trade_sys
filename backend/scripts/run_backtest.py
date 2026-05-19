#!/usr/bin/env python3
"""
简单策略回测 - 使用真实数据

功能：
- 加载特征数据
- 实现简单策略
- 运行回测
- 展示结果
"""

from pathlib import Path
from typing import Dict, Optional, List, Any
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
    commission: float = 0.001  # 0.1%
    slippage: float = 0.0005    # 0.05%
    position_size: float = 0.1  # 10%
    stop_loss: float = 0.02    # 2%
    take_profit: float = 0.05   # 5%


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
        """从DataFrame加载数据"""
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

    def run(
        self,
        signal_generator
    ) -> BacktestResult:
        """运行回测"""
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


def rsi_strategy(bar: Bar, position: Optional[Dict]) -> SignalType:
    """基于RSI的策略"""
    if not bar.features:
        return SignalType.HOLD

    rsi = bar.features.get("rsi_14")

    if position:
        # 持仓时，RSI > 70 或者 RSI > 50 止盈
        if rsi and rsi > 70:
            return SignalType.SELL
        return SignalType.HOLD

    # 空仓时，RSI < 30 买入
    if rsi and rsi < 30:
        return SignalType.BUY

    return SignalType.HOLD


def macd_strategy(bar: Bar, position: Optional[Dict]) -> SignalType:
    """基于MACD的策略"""
    if not bar.features:
        return SignalType.HOLD

    macd = bar.features.get("macd")
    macd_signal = bar.features.get("macd_signal")

    if position:
        if macd and macd_signal and macd < macd_signal:
            return SignalType.SELL
        return SignalType.HOLD

    if macd and macd_signal and macd > macd_signal:
        return SignalType.BUY

    return SignalType.HOLD


def main():
    print("="*70)
    print("📊 策略回测 - 真实数据")
    print("="*70)

    data_path = Path("data_lake/features/binance/BTCUSDT/features.parquet")
    if not data_path.exists():
        print(f"❌ 数据文件不存在: {data_path}")
        return

    print(f"\n📥 加载数据: {data_path}")
    df = pd.read_parquet(data_path)
    print(f"   总行数: {len(df)}")
    print(f"   时间范围: {df['timestamp'].min()} 至 {df['timestamp'].max()}")

    # 取样本数据进行回测（2024年Q1）
    mask = (df['timestamp'] >= '2024-01-01') & (df['timestamp'] < '2024-04-01')
    df_backtest = df.loc[mask].copy()
    print(f"\n🎯 回测样本: {len(df_backtest)} 条 (2024 Q1)")

    config = BacktestConfig(
        initial_capital=100000,
        commission=0.001,
        slippage=0.0005,
        position_size=0.1,
        stop_loss=0.02,
        take_profit=0.05
    )

    # 回测RSI策略
    print(f"\n{'='*70}")
    print("🎯 RSI策略 (RSI<30买入, RSI>70卖出)")
    print("="*70)
    engine = BacktestEngine(config)
    engine.load_df(df_backtest)
    result_rsi = engine.run(rsi_strategy)

    m = result_rsi.metrics
    print(f"\n💰 总收益: ${m.total_return:,.2f} ({m.total_return_pct:.2%})")
    print(f"📈 夏普比率: {m.sharpe_ratio:.2f}")
    print(f"📉 最大回撤: {m.max_drawdown_pct:.2%}")
    print(f"🎯 胜率: {m.win_rate:.2%}")
    print(f"📊 总交易: {m.total_trades}")
    print(f"💰 盈亏比: {m.profit_factor:.2f}")

    # 回测MACD策略
    print(f"\n{'='*70}")
    print("🎯 MACD策略 (MACD上穿买入, 下穿卖出)")
    print("="*70)
    engine = BacktestEngine(config)
    engine.load_df(df_backtest)
    result_macd = engine.run(macd_strategy)

    m = result_macd.metrics
    print(f"\n💰 总收益: ${m.total_return:,.2f} ({m.total_return_pct:.2%})")
    print(f"📈 夏普比率: {m.sharpe_ratio:.2f}")
    print(f"📉 最大回撤: {m.max_drawdown_pct:.2%}")
    print(f"🎯 胜率: {m.win_rate:.2%}")
    print(f"📊 总交易: {m.total_trades}")
    print(f"💰 盈亏比: {m.profit_factor:.2f}")

    print("\n" + "="*70)
    print("✅ 回测完成！")
    print("="*70)


if __name__ == "__main__":
    main()
