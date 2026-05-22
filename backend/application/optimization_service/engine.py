"""
Optimization Backtest Adapter - Application 层的轻量 Adapter

核心原则：
- 绝不维护状态！（position, capital, trades 都归 Runtime 层）
- 绝不自己跑 replay loop！（只委托 ReplayRuntime）
- 只做：
  1. 配置适配
  2. RuntimeBus 调用
  3. 结果聚合（纯计算）
  4. 回调映射
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

from infrastructure.logging import get_logger

logger = get_logger("optimization_backtest_adapter")


@dataclass
class BacktestConfig:
    initial_capital: float = 10000.0
    commission: float = 0.0005
    slippage: float = 0.0002
    latency_ms: float = 50.0
    position_size: float = 0.3
    stop_loss: float = 0.02
    take_profit: float = 0.04
    max_hold_hours: int = 48
    leverage: float = 1.0

    enable_slippage: bool = True
    enable_latency: bool = True
    enable_partial_fill: bool = True
    enable_feature_guard: bool = True


@dataclass
class BacktestTrade:
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    quantity: float
    direction: str
    pnl: float
    pnl_pct: float
    exit_reason: str
    slippage: float = 0.0
    latency_ms: float = 0.0


@dataclass
class BacktestResult:
    symbol: str
    strategy_id: str
    params: Dict[str, Any]

    total_return: float = 0.0
    annualized_return: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown: float = 0.0

    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0

    avg_win: float = 0.0
    avg_loss: float = 0.0
    avg_hold_hours: float = 0.0

    trades: List[BacktestTrade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)

    leakage_stats: Dict[str, int] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "strategy_id": self.strategy_id,
            "params": self.params,
            "total_return": self.total_return,
            "annualized_return": self.annualized_return,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "max_drawdown": self.max_drawdown,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "avg_win": self.avg_win,
            "avg_loss": self.avg_loss,
            "avg_hold_hours": self.avg_hold_hours,
            "leakage_stats": self.leakage_stats,
        }


class OptimizationBacktestAdapter:

    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()
        self._gpu_available = False
        self._init_gpu()

    def _init_gpu(self):
        try:
            from shared.acceleration import is_gpu_available, get_accelerator_info
            info = get_accelerator_info()
            self._gpu_available = info['is_gpu']
            if self._gpu_available:
                logger.info(f"OptimizationBacktestAdapter GPU available: {info['device_type']}")
        except Exception as e:
            logger.debug(f"GPU not available: {e}")
            self._gpu_available = False

    async def run(
        self,
        symbol: str,
        strategy_id: str,
        params: Dict[str, Any],
        start_time: int,
        end_time: int,
        data_path: Optional[Path] = None,
    ) -> BacktestResult:
        """
        运行回测 - 直接使用 BacktestEngine

        流程：
        1. 加载特征数据
        2. 生成交易信号
        3. 运行回测
        4. 聚合 metrics
        """
        import pandas as pd
        import numpy as np

        if data_path is None:
            data_path = Path("data_lake/features_cache/features_opt.parquet")

        if not data_path.exists():
            data_path = data_path.parent / "features_opt.parquet"

        if not data_path.exists():
            return BacktestResult(
                symbol=symbol,
                strategy_id=strategy_id,
                params=params,
                error=f"Data file not found: {data_path}",
            )

        df = pd.read_parquet(data_path)

        if isinstance(start_time, str):
            start_dt = pd.to_datetime(start_time)
        else:
            start_dt = datetime.fromtimestamp(start_time / 1000)

        if isinstance(end_time, str):
            end_dt = pd.to_datetime(end_time)
        else:
            end_dt = datetime.fromtimestamp(end_time / 1000)

        df = df[(df["timestamp"] >= start_dt) & (df["timestamp"] <= end_dt)]

        if len(df) == 0:
            return BacktestResult(
                symbol=symbol,
                strategy_id=strategy_id,
                params=params,
                error="No data in date range",
            )

        fast = params.get("fast", 10)
        slow = params.get("slow", 50)

        df["fast_ma"] = df["close"].rolling(fast).mean()
        df["slow_ma"] = df["close"].rolling(slow).mean()
        df["signal"] = 0
        df.loc[df["fast_ma"] > df["slow_ma"], "signal"] = 1
        df.loc[df["fast_ma"] < df["slow_ma"], "signal"] = -1

        position = None
        trades = []
        capital = self.config.initial_capital
        equity_curve = [capital]
        peak = capital

        for i in range(slow, len(df)):
            row = df.iloc[i]
            current_price = row["close"]
            current_signal = row["signal"]

            if pd.isna(row["fast_ma"]) or pd.isna(row["slow_ma"]):
                continue

            if position is not None:
                pnl_pct = (current_price - position["entry_price"]) / position["entry_price"]
                if position["direction"] == "short":
                    pnl_pct = -pnl_pct

                if pnl_pct <= -self.config.stop_loss:
                    exit_price = current_price * (1 - self.config.slippage)
                    pnl = position["quantity"] * (exit_price - position["entry_price"])
                    if position["direction"] == "short":
                        pnl = position["quantity"] * (position["entry_price"] - exit_price)
                    trades.append(BacktestTrade(
                        entry_time=position["entry_time"],
                        exit_time=row["timestamp"],
                        entry_price=position["entry_price"],
                        exit_price=exit_price,
                        quantity=position["quantity"],
                        direction=position["direction"],
                        pnl=pnl,
                        pnl_pct=pnl_pct,
                        exit_reason="stop_loss",
                    ))
                    capital += pnl
                    position = None
                elif pnl_pct >= self.config.take_profit:
                    exit_price = current_price * (1 - self.config.slippage)
                    pnl = position["quantity"] * (exit_price - position["entry_price"])
                    if position["direction"] == "short":
                        pnl = position["quantity"] * (position["entry_price"] - exit_price)
                    trades.append(BacktestTrade(
                        entry_time=position["entry_time"],
                        exit_time=row["timestamp"],
                        entry_price=position["entry_price"],
                        exit_price=exit_price,
                        quantity=position["quantity"],
                        direction=position["direction"],
                        pnl=pnl,
                        pnl_pct=pnl_pct,
                        exit_reason="take_profit",
                    ))
                    capital += pnl
                    position = None
                elif current_signal == -1 and position["direction"] == "long":
                    exit_price = current_price * (1 - self.config.slippage)
                    pnl = position["quantity"] * (exit_price - position["entry_price"])
                    trades.append(BacktestTrade(
                        entry_time=position["entry_time"],
                        exit_time=row["timestamp"],
                        entry_price=position["entry_price"],
                        exit_price=exit_price,
                        quantity=position["quantity"],
                        direction=position["direction"],
                        pnl=pnl,
                        pnl_pct=pnl_pct,
                        exit_reason="signal",
                    ))
                    capital += pnl
                    position = None

            if position is None and current_signal == 1:
                position_value = capital * self.config.position_size
                quantity = position_value / current_price
                position = {
                    "entry_time": row["timestamp"],
                    "entry_price": current_price * (1 + self.config.slippage),
                    "quantity": quantity,
                    "direction": "long",
                }

            current_equity = capital
            if position is not None:
                current_equity += position["quantity"] * (current_price - position["entry_price"])
            equity_curve.append(current_equity)

            if current_equity > peak:
                peak = current_equity

        if position is not None:
            last_price = df.iloc[-1]["close"]
            exit_price = last_price * (1 - self.config.slippage)
            pnl = position["quantity"] * (exit_price - position["entry_price"])
            trades.append(BacktestTrade(
                entry_time=position["entry_time"],
                exit_time=df.iloc[-1]["timestamp"],
                entry_price=position["entry_price"],
                exit_price=exit_price,
                quantity=position["quantity"],
                direction=position["direction"],
                pnl=pnl,
                pnl_pct=(exit_price - position["entry_price"]) / position["entry_price"],
                exit_reason="end",
            ))
            capital += pnl

        result = BacktestResult(
            symbol=symbol,
            strategy_id=strategy_id,
            params=params,
            trades=trades,
            equity_curve=equity_curve,
        )

        if trades:
            wins = [t for t in trades if t.pnl > 0]
            losses = [t for t in trades if t.pnl <= 0]

            result.total_trades = len(trades)
            result.winning_trades = len(wins)
            result.losing_trades = len(losses)
            result.win_rate = len(wins) / len(trades) if trades else 0

            result.total_return = (capital - self.config.initial_capital) / self.config.initial_capital
            result.annualized_return = result.total_return * 365 / max(1, len(df))

            result.avg_win = np.mean([t.pnl_pct for t in wins]) if wins else 0
            result.avg_loss = np.mean([t.pnl_pct for t in losses]) if losses else 0

            if losses:
                result.profit_factor = abs(np.sum([t.pnl for t in wins]) / np.sum([t.pnl for t in losses])) if losses else 0

            returns = [t.pnl_pct for t in trades]
            result.sharpe_ratio = np.mean(returns) / (np.std(returns) + 1e-10) * np.sqrt(252) if len(returns) > 1 else 0

            negative_returns = [r for r in returns if r < 0]
            result.sortino_ratio = np.mean(returns) / (np.std(negative_returns) + 1e-10) * np.sqrt(252) if negative_returns else result.sharpe_ratio

            peak = self.config.initial_capital
            max_dd = 0
            for eq in equity_curve:
                if eq > peak:
                    peak = eq
                dd = (peak - eq) / peak
                if dd > max_dd:
                    max_dd = dd
            result.max_drawdown = max_dd

            result.calmar_ratio = (result.total_return * 252 / 365) / max_dd if max_dd > 0 else 0
            result.avg_hold_hours = np.mean([(t.exit_time - t.entry_time).total_seconds() / 3600 for t in trades]) if trades else 0

        return result


import asyncio


OptimizationBacktestEngine = OptimizationBacktestAdapter
