"""
Alpha IC Module

IC 分析模块

迁移的文件：
- ic_analysis.py -> analysis.py
"""

from research.alpha.ic.analysis import (
    compute_ic_table,
    compute_conditional_ic,
)

__all__ = [
    "compute_ic_table",
    "compute_conditional_ic",
]
