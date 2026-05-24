"""
Deprecated: 此模块已迁移至 application.config.defaults.business.datasource
请使用: from application.config.defaults.business.datasource import DATASOURCE_CONFIGS, DATASOURCE_SCHEMAS
"""

import warnings

warnings.warn(
    "infrastructure.config.defaults.business.datasource is deprecated, use application.config.defaults.business.datasource instead",
    DeprecationWarning,
    stacklevel=2,
)

from application.config.defaults.business.datasource import (  # noqa: F401
    DATASOURCE_CONFIGS, DATASOURCE_SCHEMAS, KOL_TRADER_LIST, MULTI_SOURCE_CONFIG,
)
