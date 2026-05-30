import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from runtime.kernel.runtime_container import RuntimeContainer, RuntimeConfig
from runtime.kernel.runtime_context import RuntimeContext
from runtime.kernel.runtime_context import RuntimeState
from runtime.components.context_runner import ContextRunner
from runtime.components.strategy_runner import StrategyRunner

__all__ = ["BacktestResult", "BacktestRuntime"]


@dataclass
class BacktestResult:
    equity_curve: List[Dict[str, Any]]
    trades: List[Dict[str, Any]]
    metrics: Dict[str, Any]
    final_capital: float
    total_return_pct: float
    max_drawdown_pct: float
    sharpe_ratio: Optional[float] = None


class BacktestRuntime(RuntimeContainer):

    def __init__(
        self,
        config: Optional[RuntimeConfig],
        context_runner: ContextRunner,
        strategy_runner: StrategyRunner,
        execution_engine: Any,
        logger: logging.Logger,
        now_ms: int,
    ):
        super().__init__(config=config, logger=logger, now_ms=now_ms)
        self.context_runner = context_runner
        self.strategy_runner = strategy_runner
        self.execution_engine = execution_engine

    async def initialize(self) -> None:
        self.logger.info("BacktestRuntime initializing")

    async def run(self) -> None:
        raise NotImplementedError("Use run_backtest() instead")

    async def shutdown(self) -> None:
        self.logger.info("BacktestRuntime shutting down")

    def run_backtest(
        self,
        symbol: str,
        strategy_id: str,
        params: Dict[str, Any],
        start: int,
        end: int,
        capital: float,
    ) -> BacktestResult:
        raise NotImplementedError("Historical data loading not yet implemented")

    def _check_time_causality(self, current_ts: int, last_ts: int) -> bool:
        return current_ts >= last_ts
