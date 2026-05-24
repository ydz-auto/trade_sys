"""
Deprecated: 此模块已迁移至 application.config.defaults.business.risk
请使用: from application.config.defaults.business.risk import RISK_CONFIGS, RISK_SCHEMAS
"""

import warnings

warnings.warn(
    "infrastructure.config.defaults.business.risk is deprecated, use application.config.defaults.business.risk instead",
    DeprecationWarning,
    stacklevel=2,
)

from application.config.defaults.business.risk import RISK_CONFIGS, RISK_SCHEMAS  # noqa: F401
