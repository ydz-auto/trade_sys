"""
Deprecated: 此模块已迁移至 application.config.defaults.business.notification
请使用: from application.config.defaults.business.notification import NOTIFICATION_CONFIGS, NOTIFICATION_SCHEMAS
"""

import warnings

warnings.warn(
    "infrastructure.config.defaults.business.notification is deprecated, use application.config.defaults.business.notification instead",
    DeprecationWarning,
    stacklevel=2,
)

from application.config.defaults.business.notification import NOTIFICATION_CONFIGS, NOTIFICATION_SCHEMAS  # noqa: F401
