"""
Skill Adapter Layer - 适配器入口

职责：
- 提供统一的适配器入口
- 向后兼容导入

注意：
- OdailyAdapter 已迁移到 odaily_adapter.py
- 其他适配器保留在本文件
"""

from .odaily_adapter import OdailyAdapter, get_odaily_adapter
from .base import BaseAdapter, AdapterConfig

# 向后兼容别名
OdailySkillAdapter = OdailyAdapter
SkillAdapter = BaseAdapter

__all__ = [
    "OdailyAdapter",
    "OdailySkillAdapter",
    "get_odaily_adapter",
    "SkillAdapter",
    "BaseAdapter",
    "AdapterConfig",
]
