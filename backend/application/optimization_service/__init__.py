"""
Optimization Service - 策略参数优化服务

基于 Runtime 体系的参数优化，确保优化结果与实盘一致。

架构：
    Optimization API
        ↓
    OptimizationService (应用层)
        ↓
    OptimizationBacktestEngine
        ↓
    ReplayRuntime → SignalRuntime → ExecutionRuntime
        ↓
    OptimizationMetricsCollector
"""

from .service import OptimizationService, get_optimization_service
from .engine import OptimizationBacktestAdapter
from .strategy_adapter import StrategySignalAdapter
from .metrics_collector import OptimizationMetricsCollector
from .models import (
    OptimizationTask,
    OptimizationConfig,
    OptimizationResult,
    StrategyConfig,
    ParamGrid,
)

# 向后兼容
OptimizationBacktestEngine = OptimizationBacktestAdapter

__all__ = [
    "OptimizationService",
    "get_optimization_service",
    "OptimizationBacktestEngine",
    "OptimizationBacktestAdapter",
    "StrategySignalAdapter",
    "OptimizationMetricsCollector",
    "OptimizationTask",
    "OptimizationConfig",
    "OptimizationResult",
    "StrategyConfig",
    "ParamGrid",
]
