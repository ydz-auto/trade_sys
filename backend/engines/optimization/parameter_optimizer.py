"""
Parameter Optimizer - 参数优化器

提供参数优化功能，支持多种执行器：
- ProcessPoolExecutor: 多进程并行
- Sequential: 串行执行
- ThreadPoolExecutor: 多线程（未来扩展）
"""
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp
import logging
from itertools import product

from .parallel_backtest import run_backtest_in_subprocess, BacktestResult

logger = logging.getLogger(__name__)


@dataclass
class OptimizationConfig:
    """优化配置"""
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
    """优化结果"""
    best_params: Dict[str, Any]
    best_sharpe: float
    best_trades: int
    best_return: float
    all_results: List[BacktestResult] = field(default_factory=list)
    elapsed_time: float = 0.0
    num_combinations: int = 0
    num_workers: int = 0


class ParameterOptimizer:
    """
    参数优化器
    
    支持多进程并行优化参数组合
    
    Example:
        optimizer = ParameterOptimizer(
            executor="process",
            max_workers=15,
            enable_gpu=True
        )
        
        result = optimizer.optimize(
            strategy_id="long_liquidation_bounce",
            param_grid={
                "drop_threshold": [-0.015, -0.02, -0.025],
                "rsi_threshold": [20, 25, 30],
                "volume_ratio_threshold": [1.5, 2.0, 2.5]
            },
            bars_data=bars_data,
            funding_data=funding_df.to_dict("records"),
            oi_data=oi_df.to_dict("records")
        )
        
        print(f"Best params: {result.best_params}")
        print(f"Best Sharpe: {result.best_sharpe}")
    """
    
    def __init__(
        self,
        executor: str = "process",
        max_workers: Optional[int] = None,
        enable_gpu: bool = False,
        config: Optional[OptimizationConfig] = None
    ):
        """
        初始化参数优化器
        
        Args:
            executor: 执行器类型，"process" | "sequential"
            max_workers: 最大工作进程数，None表示自动检测
            enable_gpu: 是否启用GPU加速
            config: 优化配置
        """
        self.executor = executor
        self.enable_gpu = enable_gpu
        self.config = config or OptimizationConfig()
        
        if max_workers is None:
            self.max_workers = max(1, mp.cpu_count() - 1)
        else:
            self.max_workers = max_workers
        
        logger.info(f"ParameterOptimizer initialized: executor={executor}, max_workers={self.max_workers}, enable_gpu={enable_gpu}")
    
    def _generate_param_combinations(self, param_grid: Dict[str, List[Any]]) -> List[Dict[str, Any]]:
        """生成参数组合"""
        keys = list(param_grid.keys())
        values = list(param_grid.values())
        combinations = product(*values)
        return [dict(zip(keys, combo)) for combo in combinations]
    
    def _prepare_args_list(
        self,
        strategy_id: str,
        param_combinations: List[Dict[str, Any]],
        bars_data: List[Dict],
        funding_data: Optional[List],
        oi_data: Optional[List]
    ) -> List[tuple]:
        """准备子进程参数列表"""
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
            (strategy_id, params, bars_data, config_dict, self.enable_gpu, funding_data, oi_data)
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
        """
        运行参数优化
        
        Args:
            strategy_id: 策略ID
            param_grid: 参数网格
            bars_data: K线数据（序列化后的列表）
            funding_data: 资金费率数据
            oi_data: OI数据
            objective: 优化目标，"sharpe" | "return" | "trades"
        
        Returns:
            OptimizationResult: 优化结果
        """
        import time
        start_time = time.time()
        
        param_combinations = self._generate_param_combinations(param_grid)
        num_combinations = len(param_combinations)
        
        logger.info(f"Optimizing {strategy_id} with {num_combinations} param combinations")
        
        all_results: List[BacktestResult] = []
        best_sharpe = -float('inf')
        best_params = None
        best_trades = 0
        best_return = 0.0
        
        args_list = self._prepare_args_list(
            strategy_id, param_combinations, bars_data, funding_data, oi_data
        )
        
        if self.executor == "process" and num_combinations > 1:
            max_workers = min(self.max_workers, num_combinations)
            logger.info(f"Using multiprocess parallel optimization: {num_combinations} combos, max_workers={max_workers}")
            
            with ProcessPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(run_backtest_in_subprocess, args): params
                    for args, params in zip(args_list, param_combinations)
                }
                
                completed = 0
                for future in as_completed(futures):
                    params = futures[future]
                    try:
                        result = future.result()
                        completed += 1
                        
                        all_results.append(result)
                        
                        if result.sharpe is not None and result.sharpe > best_sharpe:
                            best_sharpe = result.sharpe
                            best_params = result.params
                            best_trades = result.total_trades
                            best_return = result.total_return
                        
                        if completed % 10 == 0 or completed == num_combinations:
                            logger.info(f"  Progress: {completed}/{num_combinations} (best_sharpe={best_sharpe:.4f})")
                    
                    except Exception as e:
                        logger.warning(f"Backtest failed for params {params}: {e}")
        
        else:
            logger.info(f"Using sequential optimization: {num_combinations} combos")
            
            for i, args in enumerate(args_list):
                try:
                    result = run_backtest_in_subprocess(args)
                    
                    all_results.append(result)
                    
                    if result.sharpe is not None and result.sharpe > best_sharpe:
                        best_sharpe = result.sharpe
                        best_params = result.params
                        best_trades = result.total_trades
                        best_return = result.total_return
                    
                    if (i + 1) % 10 == 0:
                        logger.info(f"  Progress: {i + 1}/{num_combinations} (best_sharpe={best_sharpe:.4f})")
                
                except Exception as e:
                    logger.warning(f"Backtest failed for params {param_combinations[i]}: {e}")
        
        elapsed_time = time.time() - start_time
        
        logger.info(f"Optimization complete: best_params={best_params}, sharpe={best_sharpe:.4f}, elapsed={elapsed_time:.2f}s")
        
        return OptimizationResult(
            best_params=best_params or {},
            best_sharpe=best_sharpe,
            best_trades=best_trades,
            best_return=best_return,
            all_results=all_results,
            elapsed_time=elapsed_time,
            num_combinations=num_combinations,
            num_workers=min(self.max_workers, num_combinations) if self.executor == "process" else 1
        )


class WalkForwardOptimizer:
    """
    Walk-Forward 优化器
    
    在多个时间窗口上运行 Walk-Forward 分析
    """
    
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
        """
        运行 Walk-Forward 分析
        
        Args:
            strategy_id: 策略ID
            param_grid: 参数网格
            train_bars: 训练期数据
            validation_bars: 验证期数据
            test_bars: 测试期数据
            funding_data: 资金费率数据
            oi_data: OI数据
        
        Returns:
            Dict: Walk-Forward 结果
        """
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
            decay_ratio = (train_result.best_sharpe - test_result.sharpe) / train_result.best_sharpe
        
        return {
            "best_params": best_params,
            "train_sharpe": train_result.best_sharpe,
            "validation_sharpe": validation_result.sharpe,
            "test_sharpe": test_result.sharpe,
            "train_trades": train_result.best_trades,
            "validation_trades": validation_result.total_trades,
            "test_trades": test_result.total_trades,
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
    ) -> BacktestResult:
        """运行单次回测"""
        args = (
            strategy_id, params, bars_data,
            {
                "initial_capital": self.optimizer.config.initial_capital,
                "commission": self.optimizer.config.commission,
                "slippage": self.optimizer.config.slippage,
                "position_size": self.optimizer.config.position_size,
                "stop_loss": self.optimizer.config.stop_loss,
                "take_profit": self.optimizer.config.take_profit,
                "leverage": self.optimizer.config.leverage,
                "use_realistic_fees": self.optimizer.config.use_realistic_fees,
            },
            self.optimizer.enable_gpu,
            funding_data,
            oi_data
        )
        
        return run_backtest_in_subprocess(args)
