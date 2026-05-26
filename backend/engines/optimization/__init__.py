"""
Engines Optimization Module

提供参数优化功能，使用统一的 AccelerationService 架构：

- ParameterOptimizer: 参数优化器
- WalkForwardOptimizer: Walk-Forward 优化器
- backtest_worker: 子进程回测函数（可被 pickle）

架构：
    脚本层 (scripts/run_walkforward_fixed.py)
        ↓
    ParameterOptimizer / WalkForwardOptimizer
        ↓
    AccelerationService (infrastructure/acceleration)
        ↓
    CPUExecutor / GPUExecutor
        ↓
    run_single_backtest_worker (backend/engines/optimization/backtest_worker)
        ↓
    StrategyRegistry (统一策略注册)

用法：
    from engines.optimization import ParameterOptimizer

    optimizer = ParameterOptimizer(
        enable_multiprocess=True,
        enable_gpu=True,
        max_workers=15
    )

    result = optimizer.optimize(...)
"""
from .parameter_optimizer import (
    ParameterOptimizer,
    OptimizationConfig,
    OptimizationResult,
    WalkForwardOptimizer
)
from .backtest_worker import (
    run_single_backtest_worker,
    build_backtest_task
)

__all__ = [
    "ParameterOptimizer",
    "OptimizationConfig",
    "OptimizationResult",
    "WalkForwardOptimizer",
    "run_single_backtest_worker",
    "build_backtest_task",
]
