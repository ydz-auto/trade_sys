"""
Engines Optimization Module

提供参数优化功能，包括：
- ParallelExecutor: 通用并行执行器
- GridSearchOptimizer: Grid Search 参数优化器
- BacktestResult: 回测结果数据结构
- backtest_worker: 子进程回测函数
"""

from .parallel_executor import (
    ParallelExecutor,
    GridSearchOptimizer,
    BacktestTaskResult
)
from .parameter_optimizer import ParameterOptimizer, OptimizationConfig, OptimizationResult
from .backtest_worker import run_single_backtest_worker, build_backtest_task

__all__ = [
    "ParallelExecutor",
    "GridSearchOptimizer",
    "BacktestTaskResult",
    "ParameterOptimizer",
    "OptimizationConfig",
    "OptimizationResult",
    "run_single_backtest_worker",
    "build_backtest_task",
]
