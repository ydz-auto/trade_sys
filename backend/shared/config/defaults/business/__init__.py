"""
Business 配置 - 业务配置，跟业务逻辑相关
"""

from shared.config.defaults.business.trading import (
    TRADING_CONFIGS,
    TRADING_SCHEMAS,
)
from shared.config.defaults.business.risk import (
    RISK_CONFIGS,
    RISK_SCHEMAS,
)
from shared.config.defaults.business.strategy import (
    STRATEGY_CONFIGS,
    STRATEGY_SCHEMAS,
)
from shared.config.defaults.business.market import (
    MARKET_CONFIGS,
    MARKET_SCHEMAS,
)
from shared.config.defaults.business.datasource import (
    DATASOURCE_CONFIGS,
    DATASOURCE_SCHEMAS,
    KOL_TRADER_LIST,
    MULTI_SOURCE_CONFIG,
)
from shared.config.defaults.business.notification import (
    NOTIFICATION_CONFIGS,
    NOTIFICATION_SCHEMAS,
)
from shared.config.defaults.business.correlation import (
    CORRELATION_CONFIGS,
    CORRELATION_SCHEMAS,
)

__all__ = [
    "TRADING_CONFIGS",
    "TRADING_SCHEMAS",
    "RISK_CONFIGS",
    "RISK_SCHEMAS",
    "STRATEGY_CONFIGS",
    "STRATEGY_SCHEMAS",
    "MARKET_CONFIGS",
    "MARKET_SCHEMAS",
    "DATASOURCE_CONFIGS",
    "DATASOURCE_SCHEMAS",
    "KOL_TRADER_LIST",
    "MULTI_SOURCE_CONFIG",
    "NOTIFICATION_CONFIGS",
    "NOTIFICATION_SCHEMAS",
    "CORRELATION_CONFIGS",
    "CORRELATION_SCHEMAS",
]
