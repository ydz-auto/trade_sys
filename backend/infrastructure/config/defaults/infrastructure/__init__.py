"""
Infrastructure 配置 - 基础配置，所有服务共用
"""

from infrastructure.config.defaults.infrastructure.cache import (
    CACHE_CONFIGS,
    CACHE_TTL,
    CACHE_DB_ALLOCATION,
    KEY_NAMING_CONVENTION,
    CACHE_KEY_PATTERNS,
    DEFAULT_TTL,
)
from infrastructure.config.defaults.infrastructure.logging import (
    LOGGING_CONFIGS,
    LOG_CONFIG,
    LOG_LEVELS,
    LOG_FORMAT,
)
from infrastructure.config.defaults.infrastructure.monitoring import (
    MONITORING_CONFIGS,
    SYSTEM_HEALTH_METRICS,
    TRADING_PERFORMANCE_METRICS,
    RISK_METRICS,
)
from infrastructure.config.defaults.infrastructure.alerting import (
    ALERTING_CONFIGS,
    ALERT_SEVERITY_CONFIG,
    ALERT_CATEGORIES,
    ALL_ALERT_RULES,
)
from infrastructure.config.defaults.infrastructure.middleware import (
    MIDDLEWARE_CONFIGS,
    KAFKA_TOPICS,
    MIDDLEWARE_SERVICE_DEPENDENCIES,
)
from infrastructure.config.defaults.infrastructure.api_gateway import (
    API_GATEWAY_CONFIGS,
    API_ROUTES,
    RATE_LIMITS,
    PERMISSIONS,
    ERROR_CODES,
)
from infrastructure.config.defaults.infrastructure.database import (
    DATABASE_CONFIGS,
    CLICKHOUSE_CONFIGS,
    POOL_CONFIGS,
)

__all__ = [
    "CACHE_CONFIGS",
    "CACHE_TTL",
    "CACHE_DB_ALLOCATION",
    "KEY_NAMING_CONVENTION",
    "CACHE_KEY_PATTERNS",
    "DEFAULT_TTL",
    "LOGGING_CONFIGS",
    "LOG_CONFIG",
    "LOG_LEVELS",
    "LOG_FORMAT",
    "MONITORING_CONFIGS",
    "SYSTEM_HEALTH_METRICS",
    "TRADING_PERFORMANCE_METRICS",
    "RISK_METRICS",
    "ALERTING_CONFIGS",
    "ALERT_SEVERITY_CONFIG",
    "ALERT_CATEGORIES",
    "ALL_ALERT_RULES",
    "MIDDLEWARE_CONFIGS",
    "KAFKA_TOPICS",
    "MIDDLEWARE_SERVICE_DEPENDENCIES",
    "API_GATEWAY_CONFIGS",
    "API_ROUTES",
    "RATE_LIMITS",
    "PERMISSIONS",
    "ERROR_CODES",
    "DATABASE_CONFIGS",
    "CLICKHOUSE_CONFIGS",
    "POOL_CONFIGS",
]
