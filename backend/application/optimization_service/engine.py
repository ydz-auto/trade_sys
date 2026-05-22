"""
Optimization Backtest Adapter - Application 层的轻量 Adapter

核心原则：
- 绝不维护状态！（position, capital, trades 都归 Runtime 层）
- 绝不自己跑 replay loop！（完全委托 ReplayRuntime）
- 只做：
  1. 配置适配
  2. Runtime 注入
  3. 结果聚合（纯计算）
  4. 回调映射

现在真正实现：Application → ReplayRuntime（不再自己做 replay）
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

from infrastructure.logging import get_logger
from runtime.replay_runtime import get_replay_runtime, SessionState

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

    真正的职责：
    - 配置适配和验证
    - 注入依赖（Feature/Signal/Execution Runtime）
    - 调用 ReplayRuntime.run_backtest()
    - 聚合结果（纯计算）

    禁止：
    - 维护任何状态（position, capital, trades）
    - 自己跑 replay loop
    - 直接调用 pandas
    """

    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()
        self._replay_runtime = None
        self._gpu_available = False
        self._init_gpu()
        self._init_runtime()

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

    def _init_runtime(self):
        """初始化 ReplayRuntime 并注入依赖"""
        self._replay_runtime = get_replay_runtime()
        
        try:
            from runtime.feature_matrix_runtime import get_feature_matrix_runtime
            from runtime.signal_runtime import get_signal_runtime
            from runtime.execution_runtime import get_execution_runtime
            
            self._replay_runtime.attach_feature_runtime(get_feature_matrix_runtime())
            self._replay_runtime.attach_signal_runtime(get_signal_runtime())
            self._replay_runtime.attach_execution_runtime(get_execution_runtime())
            
            logger.info("ReplayRuntime dependencies attached")
        except Exception as e:
            logger.warning(f"Failed to attach runtime dependencies: {e}")

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

        这是真正的 Runtime-Oriented 调用方式：
        Application → ReplayRuntime.run_backtest() → SessionState

        Args:
            symbol: 交易对
            strategy_id: 策略 ID
            params: 策略参数
            start_time: 开始时间（毫秒）
            end_time: 结束时间（毫秒）
            data_path: 数据源路径

        Returns:
            BacktestResult: 聚合后的回测结果
        """
        if not self._replay_runtime:
            raise RuntimeError("ReplayRuntime not initialized")

        logger.info(f"Running backtest via ReplayRuntime: {symbol}, {strategy_id}")

        try:
            session_state: SessionState = await self._replay_runtime.run_backtest(
                symbol=symbol,
                strategy_id=strategy_id,
                params=params,
                start_time_ms=start_time,
                end_time_ms=end_time,
                initial_capital=self.config.initial_capital,
                data_path=str(data_path) if data_path else None,
            )

            return self._aggregate_results(session_state, symbol, strategy_id, params)

        except Exception as e:
            logger.error(f"Backtest failed: {e}")
            return BacktestResult(
                symbol=symbol,
                strategy_id=strategy_id,
                params=params,
                error=str(e)
            )

    def _aggregate_results(
        self,
        session_state: SessionState,
        symbol: str,
        strategy_id: str,
        params: Dict[str, Any],
    ) -> BacktestResult:
        """聚合回测结果（纯计算，无副作用）"""
        import numpy as np

        result = BacktestResult(
            symbol=symbol,
            strategy_id=strategy_id,
            params=params,
        )

        result.equity_curve = session_state.equity_curve
        result.total_trades = len(session_state.trades)
        result.total_return = (session_state.capital - self.config.initial_capital) / self.config.initial_capital if self.config.initial_capital > 0 else 0
        result.annualized_return = result.total_return * 252 / 365

        if session_state.trades:
            wins = [t for t in session_state.trades if t.get('pnl', 0) > 0]
            losses = [t for t in session_state.trades if t.get('pnl', 0) <= 0]
            
            result.winning_trades = len(wins)
            result.losing_trades = len(losses)
            result.win_rate = len(wins) / len(session_state.trades) if session_state.trades else 0

            total_wins = sum(t.get('pnl', 0) for t in wins)
            total_losses = abs(sum(t.get('pnl', 0) for t in losses))
            result.profit_factor = total_wins / total_losses if total_losses > 0 else 0

            returns = [t.get('pnl', 0) / self.config.initial_capital for t in session_state.trades]
            result.sharpe_ratio = np.mean(returns) / (np.std(returns) + 1e-10) * np.sqrt(252) if returns else 0

            negative_returns = [r for r in returns if r < 0]
            result.sortino_ratio = np.mean(returns) / (np.std(negative_returns) + 1e-10) * np.sqrt(252) if negative_returns else result.sharpe_ratio

            peak = self.config.initial_capital
            max_dd = 0
            for eq in session_state.equity_curve:
                if eq > peak:
                    peak = eq
                dd = (peak - eq) / peak
                if dd > max_dd:
                    max_dd = dd
            result.max_drawdown = max_dd
            result.calmar_ratio = (result.total_return * 252 / 365) / max_dd if max_dd > 0 else 0

            result.avg_win = np.mean([t.get('pnl', 0) for t in wins]) / self.config.initial_capital if wins else 0
            result.avg_loss = np.mean([t.get('pnl', 0) for t in losses]) / self.config.initial_capital if losses else 0

        return result

    async def run_batch(
        self,
        tasks: List[Dict[str, Any]]
    ) -> Dict[str, BacktestResult]:
        """批量运行回测"""
        results = {}
        
        for task in tasks:
            result = await self.run(
                symbol=task['symbol'],
                strategy_id=task['strategy_id'],
                params=task.get('params', {}),
                start_time=task['start_time'],
                end_time=task['end_time'],
                data_path=task.get('data_path'),
            )
            key = f"{task['symbol']}_{task['strategy_id']}"
            results[key] = result
        
        return results


import asyncio