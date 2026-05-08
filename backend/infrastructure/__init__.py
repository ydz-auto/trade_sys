"""
TradeAgent Infrastructure Module
基础设施模块
提供日志、监控、数据库、缓存、API网关、告警等基础设施服务

使用延迟导入：子模块在首次访问时才加载，避免可选模块失败时阻塞启动
"""

__version__ = "1.0.0"

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrastructure.logging import (
        LoggerFactory,
        LoggerAdapter,
        JSONFormatter,
        TextFormatter,
        LogContext,
    )
    from infrastructure.monitoring import (
        HealthChecker,
        MetricsCollector,
        metrics_collector,
        AlertManager,
        AlertSender,
        DashboardProvider,
    )
    from infrastructure.database import (
        PostgresManager,
        get_postgres_manager,
        ClickHouseManager,
        get_clickhouse_manager,
    )
    from infrastructure.cache import (
        RedisClient,
        get_redis_client,
        CacheManager,
        get_cache_manager,
        CacheKey,
        CacheCircuitBreaker,
    )


_LAZY_SUBMODULES = {
    "logging": [
        "LoggerFactory",
        "LoggerAdapter",
        "get_logger",
        "JSONFormatter",
        "TextFormatter",
        "LogContext",
    ],
    "monitoring": [
        "HealthChecker",
        "MetricsCollector",
        "metrics_collector",
        "AlertManager",
        "AlertSender",
        "DashboardProvider",
    ],
    "database": [
        "PostgresManager",
        "get_postgres_manager",
        "ClickHouseManager",
        "get_clickhouse_manager",
    ],
    "cache": [
        "RedisClient",
        "get_redis_client",
        "CacheManager",
        "get_cache_manager",
        "CacheKey",
        "CacheCircuitBreaker",
    ],
    "api_gateway": [
        "Router",
        "AuthMiddleware",
        "RateLimitMiddleware",
        "Response",
        "APIResponse",
        "APIKeyAuth",
        "JWTAuth",
        "PermissionChecker",
    ],
    "alerting": [
        "AlertSender",
        "AlertRule",
        "AlertRuleEngine",
        "TelegramChannel",
        "EmailChannel",
        "SMSChannel",
    ],
    "messaging": [
        "KafkaBroker",
        "SchemaRegistry",
        "get_schema_registry",
    ],
    "websocket": [
        "WebSocketManager",
        "ConnectionManager",
    ],
    "scheduler": [
        "CeleryScheduler",
    ],
    "webhook": [
        "WebhookReceiver",
    ],
}

_LOADED_MODULES = {}
_FAILED_MODULES = {}


def __getattr__(name: str):
    if name in _LOADED_MODULES:
        return _LOADED_MODULES[name]

    for submodule, exports in _LAZY_SUBMODULES.items():
        if name in exports:
            try:
                module = __import__(f"infrastructure.{submodule}", fromlist=[name])
                obj = getattr(module, name)
                _LOADED_MODULES[name] = obj
                return obj
            except ImportError as e:
                _FAILED_MODULES[name] = str(e)
                raise AttributeError(
                    f"Module '{name}' is not available. "
                    f"Failed to import infrastructure.{submodule}: {e}"
                )

    raise AttributeError(f"module 'infrastructure' has no attribute '{name}'")


def __dir__():
    public_attrs = ["__version__"]
    for exports in _LAZY_SUBMODULES.values():
        public_attrs.extend(exports)
    return public_attrs


__all__ = list(__dir__())
