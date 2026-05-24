"""
Deprecated: 业务配置已迁移至 application.config.defaults.business
请使用: from application.config.defaults.business import ...
"""

import warnings

warnings.warn(
    "infrastructure.config.defaults.business is deprecated, use application.config.defaults.business instead",
    DeprecationWarning,
    stacklevel=2,
)

from application.config.defaults.business import *  # noqa: F401,F403
from application.config.defaults.business import (  # noqa: F401
    RISK_CONFIGS, RISK_SCHEMAS,
    STRATEGY_CONFIGS, STRATEGY_SCHEMAS,
    TRADING_CONFIGS, TRADING_SCHEMAS,
    MARKET_CONFIGS, MARKET_SCHEMAS,
    NOTIFICATION_CONFIGS, NOTIFICATION_SCHEMAS,
    CORRELATION_CONFIGS, CORRELATION_SCHEMAS,
    DATASOURCE_CONFIGS, DATASOURCE_SCHEMAS,
    APPROVAL_CONFIGS, APPROVAL_SCHEMAS, SYMBOL_APPROVAL_CONFIGS,
)
