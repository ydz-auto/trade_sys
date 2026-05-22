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
    """
    优化回测适配器（Application 层）

    禁止：
    - 维护任何状态（position, capital, trades）
    - 自己跑 replay loop
    - 直接调用 pandas

    只做：
    - RuntimeBus 调用委托
    - 结果聚合（纯计算）
    - 策略配置映射
    """

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
        运行回测 - 完全委托给 ReplayRuntime

        流程：
        1. 发布 RuntimeBus 命令
        2. 从 Runtime 读取结果
        3. 聚合 metrics（纯计算）
        """
        from runtime.bus.runtime_bus import get_runtime_bus

        bus = get_runtime_bus()

        await bus.publish_command(
            command="run_backtest",
            target="replay_runtime",
            params={
                "symbol": symbol,
                "strategy_id": strategy_id,
                "params": params,
                "start_time_ms": start_time,
                "end_time_ms": end_time,
                "config": self.config.__dict__,
            },
            source="application.optimization",
        )

        backtest_id = f"{symbol}_{strategy_id}_{datetime.now().timestamp():.0f}"

        raw_result = await self._fetch_raw_result(bus, backtest_id)

        metrics = self._aggregate_metrics(raw_result, symbol, strategy_id, params)

        return metrics

    async def _fetch_raw_result(self, bus, backtest_id: str) -> Optional[Dict[str, Any]]:
        """从 RuntimeBus 读取结果（CQRS 读端）"""
        await asyncio.sleep(0.1)
        state = bus.get_state("backtest")
        if state and state.get(backtest_id):
            return state[backtest_id]
        return None

    def _aggregate_metrics(
        self,
        raw_result: Optional[Dict[str, Any]],
        symbol: str,
        strategy_id: str,
        params: Dict[str, Any],
    ) -> BacktestResult:
        """聚合 metrics（纯计算，无副作用）"""
        import numpy as np

        result = BacktestResult(
            symbol=symbol,
            strategy_id=strategy_id,
            params=params,
        )

        if not raw_result:
            result.error = "No result from ReplayRuntime"
            return result

        trades_raw = raw_result.get("trades", [])
        equity_curve = raw_result.get("equity_curve", [])

        for t in trades_raw:
            trade = BacktestTrade(
                entry_time=datetime.fromisoformat(t.get("entry_time")),
                exit_time=datetime.fromisoformat(t.get("exit_time")),
                entry_price=t.get("entry_price"),
                exit_price=t.get("exit_price"),
                quantity=t.get("quantity"),
                direction=t.get("direction"),
                pnl=t.get("pnl"),
                pnl_pct=t.get("pnl_pct"),
                exit_reason=t.get("exit_reason"),
                slippage=t.get("slippage", 0),
                latency_ms=t.get("latency_ms", 0),
            )
            result.trades.append(trade)

        if not result.trades:
            return result

        result.total_trades = len(result.trades)

        initial_capital = self.config.initial_capital
        final_capital = equity_curve[-1] if equity_curve else initial_capital

        result.total_return = (final_capital - initial_capital) / initial_capital if initial_capital > 0 else 0
        result.annualized_return = result.total_return * 252 / 365

        wins = [t for t in result.trades if t.pnl_pct > 0]
        losses = [t for t in result.trades if t.pnl_pct <= 0]

        result.winning_trades = len(wins)
        result.losing_trades = len(losses)
        result.win_rate = result.winning_trades / result.total_trades if result.total_trades > 0 else 0

        total_wins = sum(t.pnl_pct for t in wins)
        total_losses = abs(sum(t.pnl_pct for t in losses))
        result.profit_factor = total_wins / total_losses if total_losses > 0 else 0

        returns = [t.pnl_pct for t in result.trades]
        result.sharpe_ratio = np.mean(returns) / (np.std(returns) + 1e-10) * np.sqrt(252) if returns else 0

        negative_returns = [r for r in returns if r < 0]
        result.sortino_ratio = np.mean(returns) / (np.std(negative_returns) + 1e-10) * np.sqrt(252) if negative_returns else result.sharpe_ratio

        peak = initial_capital
        max_dd = 0
        for eq in equity_curve:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak
            if dd > max_dd:
                max_dd = dd
        result.max_drawdown = max_dd

        result.calmar_ratio = (result.total_return * 252 / 365) / max_dd if max_dd > 0 else 0

        result.avg_win = np.mean([t.pnl_pct for t in wins]) if wins else 0
        result.avg_loss = np.mean([t.pnl_pct for t in losses]) if losses else 0
        result.avg_hold_hours = np.mean([(t.exit_time - t.entry_time).total_seconds() / 3600 for t in result.trades])

        result.leakage_stats = raw_result.get("leakage_stats", {})
        result.equity_curve = equity_curve

        return result


import asyncio
