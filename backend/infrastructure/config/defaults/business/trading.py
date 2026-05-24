"""
Deprecated: 此模块已迁移至 application.config.defaults.business.trading
请使用: from application.config.defaults.business.trading import TRADING_CONFIGS, TRADING_SCHEMAS
"""

import warnings

warnings.warn(
    "infrastructure.config.defaults.business.trading is deprecated, use application.config.defaults.business.trading instead",
    DeprecationWarning,
    stacklevel=2,
)

from application.config.defaults.business.trading import TRADING_CONFIGS, TRADING_SCHEMAS  # noqa: F401
