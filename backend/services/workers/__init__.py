"""
Workers - 收敛后的服务入口

将多个微服务合并为三个 worker：
- data_worker: 数据采集 + 聚合
- strategy_worker: 事件处理 + 信号融合 + 策略决策
- execution_worker: 风控 + 执行
"""

from .data_worker import DataWorker
from .strategy_worker import StrategyWorker
from .execution_worker import ExecutionWorker

__all__ = ["DataWorker", "StrategyWorker", "ExecutionWorker"]
