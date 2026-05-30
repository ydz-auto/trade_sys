"""
Alpha Registry Module

注册中心模块

迁移的文件：
- strategy_alpha_registry.py -> alpha_registry.py
"""

from research.alpha.registry.alpha_registry import (
    AlphaRegistry,
    AlphaDefinition,
)

__all__ = [
    "AlphaRegistry",
    "AlphaDefinition",
]
