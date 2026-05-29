"""
Short Alpha Feature Factory - 做空 Alpha Feature 研究目录

这个目录专门用于研究和验证做空 Alpha Features。

结构：
├── __init__.py                    - 模块初始化
├── README.md                      - 使用文档
├── short_features_registry.py      - Short Features 注册表和统计
└── validate_short_features.py      - 独立验证脚本

Feature Families:
1. OVEREXTENSION  - 价格偏离度（涨得太离谱）
2. PARABOLIC      - 抛物线阶段（加速上涨）
3. EXHAUSTION     - 做空衰竭（买盘衰竭）
4. BREAKFAIL       - 失败突破（创新高后回落）
5. CROWDED         - 多头拥挤（杠杆/资金费率极端）

使用流水线：
Feature → IC → Conditional IC → Signal Test → WF → Stability
"""

from .short_features_registry import (
    SHORT_FEATURES_BY_FAMILY,
    ALL_SHORT_FEATURES,
    get_short_features_by_family,
    print_short_feature_summary,
)
from .validate_short_features import (
    run_short_feature_validation,
)

__all__ = [
    "SHORT_FEATURES_BY_FAMILY",
    "ALL_SHORT_FEATURES",
    "get_short_features_by_family",
    "print_short_feature_summary",
    "run_short_feature_validation",
]
