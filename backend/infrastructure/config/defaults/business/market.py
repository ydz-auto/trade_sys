"""
Deprecated: 此模块已迁移至 application.config.defaults.business.market
请使用: from application.config.defaults.business.market import MARKET_CONFIGS, MARKET_SCHEMAS
"""

import warnings

warnings.warn(
    "infrastructure.config.defaults.business.market is deprecated, use application.config.defaults.business.market instead",
    DeprecationWarning,
    stacklevel=2,
)

from application.config.defaults.business.market import MARKET_CONFIGS, MARKET_SCHEMAS  # noqa: F401
