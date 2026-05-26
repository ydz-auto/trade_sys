"""
[DEPRECATED] Parallel Executor - 通用并行执行器

这个文件已经被废弃！

使用新架构：
    infrastructure/acceleration/
        ├── device_manager.py
        ├── cpu_executor.py
        ├── gpu_executor.py
        └── acceleration_service.py

    engines/optimization/
        ├── parameter_optimizer.py
        └── backtest_worker.py

迁移示例：
    # 旧方式（已废弃）
    from engines.optimization.parallel_executor import ParallelExecutor

    # 新方式
    from engines.optimization import ParameterOptimizer
    from infrastructure.acceleration import AccelerationService
"""
import warnings

warnings.warn(
    "parallel_executor.py is deprecated! Use infrastructure/acceleration/ and engines/optimization/backtest_worker.py instead",
    DeprecationWarning,
    stacklevel=2
)

# 保存空文件避免导入错误，但不应再使用
