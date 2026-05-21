"""
Analysis Domain - 分析领域

这个模块包含核心分析模型和类型定义。

包含：
- correlation: 相关性分析核心类型
- scoring: 评分模型
- relationship: 关系分析
- clustering: 聚类分析

业务逻辑请使用：
- services/correlation_service/ - 相关性服务
- research/correlation/ - 研究分析
"""

from .types import SignalDirection

__all__ = [
    "SignalDirection",
]
