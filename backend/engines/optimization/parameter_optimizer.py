from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import logging
from itertools import product

from runtime.backtest.backtest_worker import run_single_backtest_worker, build_backtest_task
from infrastructure.acceleration import AccelerationService, AccelerationConfig

logger = logging.getLogger(__name__)


@dataclass
class OptimizationConfig:
    initial_capital: float = 10000.0
    commission: float = 0.0004
    slippage: float = 0.0005
    position_size: float = 0.1
    stop_loss: float = 0.10
    take_profit: float = 0.20
    leverage: float = 5.0
    use_realistic_fees: bool = True
    enable_gpu: bool = False


@dataclass
class OptimizationResult:
    best_params: Dict[str, Any]
    best_sharpe: float
    best_trades: int
    best_return: float
    all_results: List[Dict[str, Any]] = field(default_factory=list)
    elapsed_time: float = 0.0
    num_combinations: int = 0
    num_workers: int = 0


class ParameterOptimizer:

    def __init__(
        self,
        enable_multiprocess: bool = True,
        max_workers: Optional[int] = None,
        enable_gpu: bool = False,
        config: Optional[OptimizationConfig] = None
    ):
        self.enable_gpu = enable_gpu
        self.config = config or OptimizationConfig()

        self._acceleration_service = AccelerationService.create_for_optimization(
            enable_multiprocess=enable_multiprocess,
            enable_gpu=enable_gpu,
            max_workers=max_workers
        )

        logger.info(
            f"ParameterOptimizer initialized: "
            f"multiprocess={enable_multiprocess}, "
            f"max_workers={max_workers}, "
            f"enable_gpu={enable_gpu}"
        )

    def _generate_param_combinations(self, param_grid: Dict[str, List[Any]]) -> List[Dict[str, Any]]:
        keys = list(param_grid.keys())
        values = list(param_grid.values())
        combinations = product(*values)
        return [dict(zip(keys, combo)) for combo in combinations]

    def _build_tasks_list(
        self,
        strategy_id: str,
        param_combinations: List[Dict[str, Any]],
        bars_data: List[Dict],
        funding_data: Optional[List],
        oi_data: Optional[List]
    ) -> List[Dict[str, Any]]:
        config_dict = {
            "initial_capital": self.config.initial_capital,
            "commission": self.config.commission,
            "slippage": self.config.slippage,
            "position_size": self.config.position_size,
            "stop_loss": self.config.stop_loss,
            "take_profit": self.config.take_profit,
            "leverage": self.config.leverage,
            "use_realistic_fees": self.config.use_realistic_fees,
        }

        return [
            build_backtest_task(
                strategy_id=strategy_id,
                params=params,
                bars_data=bars_data,
                config_dict=config_dict,
                enable_gpu=self.enable_gpu,
                funding_data=funding_data,
                oi_data=oi_data
            )
            for params in param_combinations
        ]

    def optimize(
        self,
        strategy_id: str,
        param_grid: Dict[str, List[Any]],
        bars_data: List[Dict],
        funding_data: Optional[List] = None,
        oi_data: Optional[List] = None,
        objective: str = "sharpe"
    ) -> OptimizationResult:
        import time
        start_time = time.time()

        param_combinations = self._generate_param_combinations(param_grid)
        num_combinations = len(param_combinations)

        logger.info(f"Optimizing {strategy_id} with {num_combinations} param combinations")

        all_results: List[Dict[str, Any]] = []
        best_sharpe = -float('inf')
        best_params = None
        best_trades = 0
        best_return = 0.0

        tasks = self._build_tasks_list(
            strategy_id, param_combinations, bars_data, funding_data, oi_data
        )

        if num_combinations > 1:
            logger.info(f"Using AccelerationService: {num_combinations} combos")

            results = self._acceleration_service.parallel_map(
                func=run_single_backtest_worker,
                tasks=tasks,
                executor="process",
                progress_callback=lambda done, total: logger.info(
                    f"  Progress: {done}/{total}"
                )
            )

            completed = 0
            for result in results:
                if result is not None:
                    all_results.append(result)

                    sharpe = result.get("sharpe", -float('inf'))
                    if sharpe is not None and sharpe > best_sharpe:
                        best_sharpe = sharpe
                        best_params = result.get("params")
                        best_trades = result.get("trades", 0)
                        best_return = result.get("total_return", 0.0)

                completed += 1
                if completed % 10 == 0:
                    logger.info(f"  Progress: {completed}/{num_combinations} (best_sharpe={best_sharpe:.4f})")

        else:
            logger.info(f"Using sequential optimization: {num_combinations} combos")

            for i, task in enumerate(tasks):
                result = run_single_backtest_worker(task)

                if result.get("error"):
                    logger.warning(f"Backtest failed for params {task.get('params')}: {result.get('error')}")
                else:
                    all_results.append(result)

                    sharpe = result.get("sharpe", -float('inf'))
                    if sharpe is not None and sharpe > best_sharpe:
                        best_sharpe = sharpe
                        best_params = result.get("params")
                        best_trades = result.get("trades", 0)
                        best_return = result.get("total_return", 0.0)

                if (i + 1) % 10 == 0:
                    logger.info(f"  Progress: {i + 1}/{num_combinations} (best_sharpe={best_sharpe:.4f})")

        elapsed_time = time.time() - start_time

        logger.info(
            f"Optimization complete: best_params={best_params}, "
            f"sharpe={best_sharpe:.4f}, elapsed={elapsed_time:.2f}s"
        )

        return OptimizationResult(
            best_params=best_params or {},
            best_sharpe=best_sharpe,
            best_trades=best_trades,
            best_return=best_return,
            all_results=all_results,
            elapsed_time=elapsed_time,
            num_combinations=num_combinations,
            num_workers=self._acceleration_service._cpu_executor.max_workers if hasattr(self._acceleration_service, '_cpu_executor') else 1
        )
