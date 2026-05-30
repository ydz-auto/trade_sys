from typing import Dict, List, Any, Optional
import logging

from engines.optimization.parameter_optimizer import ParameterOptimizer, OptimizationResult
from runtime.backtest.backtest_worker import run_single_backtest_worker, build_backtest_task

logger = logging.getLogger(__name__)


class WalkForwardOptimizer:

    def __init__(self, optimizer: ParameterOptimizer):
        self.optimizer = optimizer

    def run_walk_forward(
        self,
        strategy_id: str,
        param_grid: Dict[str, List[Any]],
        train_bars: List[Dict],
        validation_bars: List[Dict],
        test_bars: List[Dict],
        funding_data: Optional[List] = None,
        oi_data: Optional[List] = None
    ) -> Dict[str, Any]:
        logger.info(f"Running Walk-Forward for {strategy_id}")

        train_result = self.optimizer.optimize(
            strategy_id=strategy_id,
            param_grid=param_grid,
            bars_data=train_bars,
            funding_data=funding_data,
            oi_data=oi_data
        )

        best_params = train_result.best_params

        logger.info(f"Best params from train: {best_params}")

        validation_result = self._run_single_backtest(
            strategy_id, best_params, validation_bars, funding_data, oi_data
        )

        test_result = self._run_single_backtest(
            strategy_id, best_params, test_bars, funding_data, oi_data
        )

        decay_ratio = 0.0
        if train_result.best_sharpe > 0:
            decay_ratio = (train_result.best_sharpe - test_result.get("sharpe", 0.0)) / train_result.best_sharpe

        return {
            "best_params": best_params,
            "train_sharpe": train_result.best_sharpe,
            "validation_sharpe": validation_result.get("sharpe", -float('inf')),
            "test_sharpe": test_result.get("sharpe", -float('inf')),
            "train_trades": train_result.best_trades,
            "validation_trades": validation_result.get("trades", 0),
            "test_trades": test_result.get("trades", 0),
            "decay_ratio": decay_ratio,
            "train_elapsed": train_result.elapsed_time
        }

    def _run_single_backtest(
        self,
        strategy_id: str,
        params: Dict[str, Any],
        bars_data: List[Dict],
        funding_data: Optional[List],
        oi_data: Optional[List]
    ) -> Dict[str, Any]:
        task = build_backtest_task(
            strategy_id=strategy_id,
            params=params,
            bars_data=bars_data,
            config_dict={
                "initial_capital": self.optimizer.config.initial_capital,
                "commission": self.optimizer.config.commission,
                "slippage": self.optimizer.config.slippage,
                "position_size": self.optimizer.config.position_size,
                "stop_loss": self.optimizer.config.stop_loss,
                "take_profit": self.optimizer.config.take_profit,
                "leverage": self.optimizer.config.leverage,
                "use_realistic_fees": self.optimizer.config.use_realistic_fees,
            },
            enable_gpu=self.optimizer.enable_gpu,
            funding_data=funding_data,
            oi_data=oi_data
        )

        return run_single_backtest_worker(task)
