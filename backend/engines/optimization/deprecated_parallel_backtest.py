"""
[DEPRECATED] Parallel Backtest Module - 子进程回测函数

这个文件已经被废弃！

使用新架构：
    engines/optimization/backtest_worker.py

迁移示例：
    # 旧方式（已废弃）
    from engines.optimization.parallel_backtest import run_backtest_in_subprocess

    # 新方式
    from engines.optimization.backtest_worker import (
        run_single_backtest_worker,
        build_backtest_task
    )
"""
import warnings

warnings.warn(
    "parallel_backtest.py is deprecated! Use engines/optimization/backtest_worker.py instead",
    DeprecationWarning,
    stacklevel=2
)
