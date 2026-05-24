"""
监控配置和常量定义
从 shared.config 导入
"""

from infrastructure.config.enums import ServiceStatus
from infrastructure.config.defaults.infrastructure import (
    MONITORING_CONFIGS,
    SYSTEM_HEALTH_METRICS,
    TRADING_PERFORMANCE_METRICS,
    RISK_METRICS,
)

METRICS_COLLECTION_INTERVAL = MONITORING_CONFIGS.get("monitoring.metrics_collection_interval", 60)
HEALTH_CHECK_INTERVAL = MONITORING_CONFIGS.get("monitoring.health_check_interval", 30)
ALERT_CHECK_INTERVAL = MONITORING_CONFIGS.get("monitoring.alert_check_interval", 10)


__all__ = [
    "ServiceStatus",
    "ALERT_LEVELS",
    "DEFAULT_ALERT_RULES",
    "SYSTEM_HEALTH_METRICS",
    "TRADING_PERFORMANCE_METRICS",
    "RISK_METRICS",
    "METRICS_COLLECTION_INTERVAL",
    "HEALTH_CHECK_INTERVAL",
    "ALERT_CHECK_INTERVAL",
]