"""
Deprecated: 此模块已迁移至 application.config.defaults.business.approval
请使用: from application.config.defaults.business.approval import APPROVAL_CONFIGS, ...
"""

import warnings

warnings.warn(
    "infrastructure.config.defaults.business.approval is deprecated, use application.config.defaults.business.approval instead",
    DeprecationWarning,
    stacklevel=2,
)

from application.config.defaults.business.approval import (  # noqa: F401
    APPROVAL_CONFIGS, APPROVAL_SCHEMAS, SYMBOL_APPROVAL_CONFIGS,
)
