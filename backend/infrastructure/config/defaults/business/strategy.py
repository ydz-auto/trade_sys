"""
Deprecated: 此模块已迁移至 application.config.defaults.business.strategy
请使用: from application.config.defaults.business.strategy import STRATEGY_CONFIGS, STRATEGY_SCHEMAS
"""

import warnings

warnings.warn(
    "infrastructure.config.defaults.business.strategy is deprecated, use application.config.defaults.business.strategy instead",
    DeprecationWarning,
    stacklevel=2,
)

from application.config.defaults.business.strategy import STRATEGY_CONFIGS, STRATEGY_SCHEMAS  # noqa: F401
