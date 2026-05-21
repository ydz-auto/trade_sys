"""
Backtest Service - REFACTORED

This service now acts as a facade to replay_runtime.
The actual replay logic is handled by runtime.replay_runtime.

Use replay_runtime for all time-causal replay functionality.
"""
import warnings
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime

from infrastructure.logging import get_logger

logger = get_logger("backtest_service")

warnings.warn(
    "backtest_service is now a facade. "
    "Prefer using runtime.replay_runtime directly for time-causal replay.",
    DeprecationWarning,
    stacklevel=2
)

# 导出兼容类型
try:
    from .backtest_engine import (
        BacktestEngine,
        BacktestConfig,
        BacktestResult,
        PerformanceMetrics,
        Bar,
        Trade,
        SignalType,
        MockDataGenerator,
        run_backtest,
    )
    __all__ = [
        "BacktestEngine",
        "BacktestConfig",
        "BacktestResult",
        "PerformanceMetrics",
        "Bar",
        "Trade",
        "SignalType",
        "MockDataGenerator",
        "run_backtest",
    ]
except Exception as e:
    logger.error(f"Failed to import backtest_engine: {e}")
    raise
