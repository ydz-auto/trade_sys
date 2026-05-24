"""
Deprecated: 此模块已迁移至 application.config.defaults.business.correlation
请使用: from application.config.defaults.business.correlation import CORRELATION_CONFIGS, CORRELATION_SCHEMAS
"""

import warnings

warnings.warn(
    "infrastructure.config.defaults.business.correlation is deprecated, use application.config.defaults.business.correlation instead",
    DeprecationWarning,
    stacklevel=2,
)

from application.config.defaults.business.correlation import CORRELATION_CONFIGS, CORRELATION_SCHEMAS  # noqa: F401
