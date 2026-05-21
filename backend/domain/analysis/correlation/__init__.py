"""
Correlation Analysis - 相关性分析核心

这个模块包含相关性分析的核心类型定义。

核心模型：
- types: 相关性类型定义

业务逻辑请使用：
- services/correlation_service/
- research/correlation/
"""
from domain.analysis.types import SignalDirection

__all__ = [
    "SignalDirection",
]
