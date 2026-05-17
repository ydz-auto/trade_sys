"""
Correlation Runtime - 多数据源相关性分析运行时

职责：
1. 定时执行多数据源相关性分析
2. 结果存储和可视化
3. 强信号告警

用法:
    python -m runtime.correlation_runtime
"""

from runtime.correlation_runtime.runtime import CorrelationRuntime, get_correlation_runtime

__all__ = ["CorrelationRuntime", "get_correlation_runtime"]
