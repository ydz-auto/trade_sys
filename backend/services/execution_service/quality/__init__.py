"""
Execution Quality - 执行质量服务

优化执行质量:
1. Smart Execution - 智能执行
2. Order Splitting - 订单拆分
3. Slippage Control - 滑点控制
4. Execution Analytics - 执行分析

这些是业务逻辑服务，不是核心领域模型。
"""

from .smart_execution import SmartExecution, execute_smart
from .order_splitting import OrderSplitter, split_order
from .slippage_control import SlippageController, control_slippage
from .execution_analytics import ExecutionAnalytics

__all__ = [
    "SmartExecution",
    "execute_smart",
    "OrderSplitter",
    "split_order",
    "SlippageController",
    "control_slippage",
    "ExecutionAnalytics",
]
