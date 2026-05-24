"""
Deprecated: 此模块已迁移至 runtimes.celery_tasks

请使用: from runtimes.celery_tasks import celery_app, get_celery_app
"""

import warnings

warnings.warn(
    "infrastructure.utilities.scheduler is deprecated. "
    "Use runtimes.celery_tasks instead.",
    DeprecationWarning,
    stacklevel=2,
)

try:
    from runtimes.celery_tasks import celery_app, get_celery_app
except ImportError:
    celery_app = None
    get_celery_app = None
