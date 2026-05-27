"""
Strategy (DEPRECATED) - 旧策略模块已弃用

请使用新的架构：
- engines.compute.context - MarketContext 定义
- engines.compute.strategy_v2 - V2 策略（只消费 MarketContext）

保留的内容：
- calculators - 特征计算器（仍在使用，用于生成 raw features）
"""

# calculators 模块仍在使用，保留导出
from .calculators import *

__all__: list[str] = []
