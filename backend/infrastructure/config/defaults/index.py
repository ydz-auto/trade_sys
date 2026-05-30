"""
Config Index - 合并所有领域配置

仅包含 infrastructure 层配置默认值。
业务配置（trading, risk, strategy 等）由 application 层通过
register_business_configs() 注入。
"""

from typing import Dict, Any
from infrastructure.config.enums import ConfigCategory

from .core import SYSTEM_CONFIGS, SYSTEM_SCHEMAS
from .infrastructure.logging import LOGGING_CONFIGS, LOG_CONFIG, LOG_LEVELS, LOG_FORMAT
from .infrastructure.monitoring import MONITORING_CONFIGS, SYSTEM_HEALTH_METRICS, TRADING_PERFORMANCE_METRICS, RISK_METRICS
from .infrastructure.cache import CACHE_CONFIGS, CACHE_TTL, CACHE_DB_ALLOCATION, KEY_NAMING_CONVENTION, CACHE_KEY_PATTERNS, DEFAULT_TTL
from .infrastructure.api_gateway import API_GATEWAY_CONFIGS, API_ROUTES, RATE_LIMITS, PERMISSIONS, ERROR_CODES
from .infrastructure.alerting import ALERTING_CONFIGS, ALERT_SEVERITY_CONFIG, ALERT_CATEGORIES, ALL_ALERT_RULES
from .infrastructure.middleware import MIDDLEWARE_CONFIGS, MIDDLEWARE_SCHEMAS, KAFKA_TOPICS, MIDDLEWARE_SERVICE_DEPENDENCIES
from .infrastructure.database import DATABASE_CONFIGS, CLICKHOUSE_CONFIGS, POOL_CONFIGS
from .infrastructure.external_apis import (
    EXCHANGE_REST_APIS, EXCHANGE_WS_APIS, LLM_APIS, NEWS_APIS, MACRO_APIS, ETF_APIS,
    BINANCE_REST_API, BINANCE_WS_URL, OKX_REST_API, OKX_WS_PUBLIC_URL,
    OPENAI_API_URL, ANTHROPIC_API_URL, OLLAMA_API_URL, ODAILY_BASE_URL,
)


INFRASTRUCTURE_CONFIGS: Dict[str, Any] = {
    **SYSTEM_CONFIGS,
    **LOGGING_CONFIGS,
    **MONITORING_CONFIGS,
    **CACHE_CONFIGS,
    **API_GATEWAY_CONFIGS,
    **ALERTING_CONFIGS,
    **MIDDLEWARE_CONFIGS,
    **DATABASE_CONFIGS,
    **CLICKHOUSE_CONFIGS,
    **POOL_CONFIGS,
}

INFRASTRUCTURE_SCHEMAS: Dict[str, Dict] = {
    **SYSTEM_SCHEMAS,
    **MIDDLEWARE_SCHEMAS,
}


_business_configs: Dict[str, Any] = {}
_business_schemas: Dict[str, Dict] = {}
_business_categories: Dict[ConfigCategory, list] = {}


def register_business_configs(
    configs: Dict[str, Any],
    schemas: Dict[str, Dict],
    categories: Dict[ConfigCategory, list],
) -> None:
    global _business_configs, _business_schemas, _business_categories
    _business_configs = configs
    _business_schemas = schemas
    _business_categories = categories


def get_default_configs() -> Dict[str, Any]:
    return {**INFRASTRUCTURE_CONFIGS, **_business_configs}


def get_config_schemas() -> Dict[str, Dict]:
    return {**INFRASTRUCTURE_SCHEMAS, **_business_schemas}


def get_config_categories() -> Dict[ConfigCategory, list]:
    categories = {
        ConfigCategory.LOGGING: list(LOGGING_CONFIGS.keys()),
        ConfigCategory.MONITORING: list(MONITORING_CONFIGS.keys()),
        ConfigCategory.CACHE: list(CACHE_CONFIGS.keys()),
        ConfigCategory.API_GATEWAY: list(API_GATEWAY_CONFIGS.keys()),
        ConfigCategory.ALERTING: list(ALERTING_CONFIGS.keys()),
        ConfigCategory.MIDDLEWARE: list(MIDDLEWARE_CONFIGS.keys()),
    }
    categories.update(_business_categories)
    return categories


DEFAULT_CONFIGS = INFRASTRUCTURE_CONFIGS
CONFIG_SCHEMAS = INFRASTRUCTURE_SCHEMAS
CONFIG_CATEGORIES = get_config_categories()

ALL_SCHEMAS = CONFIG_SCHEMAS


__all__ = [
    "DEFAULT_CONFIGS",
    "CONFIG_SCHEMAS",
    "CONFIG_CATEGORIES",
    "INFRASTRUCTURE_CONFIGS",
    "INFRASTRUCTURE_SCHEMAS",
    "register_business_configs",
    "get_default_configs",
    "get_config_schemas",
    "get_config_categories",
    "LOG_CONFIG",
    "LOG_LEVELS",
    "LOG_FORMAT",
    "SYSTEM_HEALTH_METRICS",
    "TRADING_PERFORMANCE_METRICS",
    "RISK_METRICS",
    "CACHE_TTL",
    "CACHE_DB_ALLOCATION",
    "KEY_NAMING_CONVENTION",
    "CACHE_KEY_PATTERNS",
    "DEFAULT_TTL",
    "API_ROUTES",
    "RATE_LIMITS",
    "PERMISSIONS",
    "ERROR_CODES",
    "ALERT_SEVERITY_CONFIG",
    "ALERT_CATEGORIES",
    "ALL_ALERT_RULES",
    "KAFKA_TOPICS",
    "MIDDLEWARE_SERVICE_DEPENDENCIES",
    "SYMBOL_APPROVAL_CONFIGS",
]
