"""
Runtime Module - 统一运行时模块

提供：
1. 统一时钟系统 (Clock)
2. 统一运行时引擎 (RuntimeEngine)
3. 四种运行模式支持 (live/paper/replay/backtest)
"""

from .clock import (
    Clock,
    ClockMode,
    ClockConfig,
    get_clock,
    set_clock,
    now,
    timestamp,
    clock_sleep,
    clock_sleep_async,
    use_clock,
)

from .engine import (
    RuntimeEngine,
    RuntimeMode,
    RuntimeConfig,
    RuntimeState,
    create_live_runtime,
    create_paper_runtime,
    create_replay_runtime,
    create_backtest_runtime,
)

__all__ = [
    "Clock",
    "ClockMode",
    "ClockConfig",
    "get_clock",
    "set_clock",
    "now",
    "timestamp",
    "clock_sleep",
    "clock_sleep_async",
    "use_clock",
    "RuntimeEngine",
    "RuntimeMode",
    "RuntimeConfig",
    "RuntimeState",
    "create_live_runtime",
    "create_paper_runtime",
    "create_replay_runtime",
    "create_backtest_runtime",
]
