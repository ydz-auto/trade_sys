"""
Config 配置模块 - 运行时配置管理

提供运行时动态配置管理，支持：
- Redis 缓存
- 用户偏好设置
- 策略参数配置
- 数据源配置

与 config/ 模块的区别：
- config/ - 静态配置（YAML 文件，部署时确定）
- shared/config/ - 运行时配置（Redis 动态，运行时可修改）

使用场景：
- 用户偏好设置
- 策略参数调整
- 数据源动态配置
- 功能开关（运行时）
"""

from infrastructure.config.enums import (
    ConfigCategory,
    ConfigScope,
    DataSourceCategory,
    LogType,
    LogLevel,
    AlertSeverity,
    AlertCategory,
    MonitoringCategory,
    ServiceStatus,
    CacheStrategy,
    HTTPMethod,
)
from infrastructure.config.schemas import (
    ConfigEntry,
    ConfigVersion,
    ConfigSchema,
)
from infrastructure.config.defaults.infrastructure import (
    LOGGING_CONFIGS,
    LOG_CONFIG,
    LOG_LEVELS,
    LOG_FORMAT,
    MONITORING_CONFIGS,
    SYSTEM_HEALTH_METRICS,
    TRADING_PERFORMANCE_METRICS,
    RISK_METRICS,
    CACHE_CONFIGS,
    CACHE_TTL,
    CACHE_DB_ALLOCATION,
    KEY_NAMING_CONVENTION,
    CACHE_KEY_PATTERNS,
    DEFAULT_TTL,
    API_GATEWAY_CONFIGS,
    API_ROUTES,
    RATE_LIMITS,
    PERMISSIONS,
    ERROR_CODES,
    ALERTING_CONFIGS,
    ALERT_SEVERITY_CONFIG,
    ALERT_CATEGORIES,
    ALL_ALERT_RULES,
    MIDDLEWARE_CONFIGS,
    KAFKA_TOPICS,
    MIDDLEWARE_SERVICE_DEPENDENCIES,
    DATABASE_CONFIGS,
    CLICKHOUSE_CONFIGS,
    POOL_CONFIGS,
)
from infrastructure.config.defaults.business import (
    TRADING_CONFIGS,
    RISK_CONFIGS,
    STRATEGY_CONFIGS,
    MARKET_CONFIGS,
    NOTIFICATION_CONFIGS,
    DATASOURCE_CONFIGS,
    DATASOURCE_SCHEMAS,
    KOL_TRADER_LIST,
    MULTI_SOURCE_CONFIG,
)
from infrastructure.config.defaults import (
    DEFAULT_CONFIGS,
    CONFIG_SCHEMAS,
    CONFIG_CATEGORIES,
    SYSTEM_CONFIGS,
)
from infrastructure.config.manager import (
    ConfigValidationError,
    ConfigNotFoundError,
    ConfigVersionConflictError,
    ConfigManager,
    StrategyConfigManager,
    UserConfigManager,
    DataSourceConfigManager,
    get_config_manager,
    get_strategy_config_manager,
    get_user_config_manager,
    get_datasource_config_manager,
)
from infrastructure.config.unified import (
    get_config,
    get_exchange_credentials,
    get_llm_credentials,
    get_api_url,
    get_strategy_weights,
    DEFAULT_API_URLS,
    DEFAULT_STRATEGY_CONFIG,
)

__all__ = [
    "ConfigCategory",
    "ConfigScope",
    "DataSourceCategory",
    "LogType",
    "LogLevel",
    "AlertSeverity",
    "AlertCategory",
    "MonitoringCategory",
    "ServiceStatus",
    "CacheStrategy",
    "HTTPMethod",
    "ConfigEntry",
    "ConfigVersion",
    "ConfigSchema",
    "DEFAULT_CONFIGS",
    "CONFIG_SCHEMAS",
    "CONFIG_CATEGORIES",
    "SYSTEM_CONFIGS",
    "TRADING_CONFIGS",
    "RISK_CONFIGS",
    "STRATEGY_CONFIGS",
    "MARKET_CONFIGS",
    "NOTIFICATION_CONFIGS",
    "DATASOURCE_CONFIGS",
    "DATASOURCE_SCHEMAS",
    "KOL_TRADER_LIST",
    "MULTI_SOURCE_CONFIG",
    "LOGGING_CONFIGS",
    "LOG_CONFIG",
    "LOG_LEVELS",
    "LOG_FORMAT",
    "MONITORING_CONFIGS",
    "SYSTEM_HEALTH_METRICS",
    "TRADING_PERFORMANCE_METRICS",
    "RISK_METRICS",
    "CACHE_CONFIGS",
    "CACHE_TTL",
    "CACHE_DB_ALLOCATION",
    "KEY_NAMING_CONVENTION",
    "CACHE_KEY_PATTERNS",
    "DEFAULT_TTL",
    "API_GATEWAY_CONFIGS",
    "API_ROUTES",
    "RATE_LIMITS",
    "PERMISSIONS",
    "ERROR_CODES",
    "ALERTING_CONFIGS",
    "ALERT_SEVERITY_CONFIG",
    "ALERT_CATEGORIES",
    "ALL_ALERT_RULES",
    "MIDDLEWARE_CONFIGS",
    "KAFKA_TOPICS",
    "MIDDLEWARE_SERVICE_DEPENDENCIES",
    "DATABASE_CONFIGS",
    "CLICKHOUSE_CONFIGS",
    "POOL_CONFIGS",
    "ConfigValidationError",
    "ConfigNotFoundError",
    "ConfigVersionConflictError",
    "ConfigManager",
    "StrategyConfigManager",
    "UserConfigManager",
    "DataSourceConfigManager",
    "get_config_manager",
    "get_strategy_config_manager",
    "get_user_config_manager",
    "get_datasource_config_manager",
    "get_config",
    "get_exchange_credentials",
    "get_llm_credentials",
    "get_api_url",
    "get_strategy_weights",
    "DEFAULT_API_URLS",
    "DEFAULT_STRATEGY_CONFIG",
]
