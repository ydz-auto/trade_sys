"""
Execution Runtime - 订单执行运行时

合并 execution_service + risk_service

职责：
1. 消费决策事件
2. 风控检查
3. 订单执行

用法:
    python -m runtime.execution_runtime
"""

from runtime.execution_runtime.runtime import ExecutionRuntime, get_execution_runtime

__all__ = ["ExecutionRuntime", "get_execution_runtime"]
