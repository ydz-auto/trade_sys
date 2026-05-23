"""
告警配置
从 shared.config 导入
"""

from infrastructure.config.enums import AlertSeverity, AlertCategory
from infrastructure.config.defaults.infrastructure import (
    ALERTING_CONFIGS,
    ALERT_SEVERITY_CONFIG,
    ALERT_CATEGORIES,
    ALL_ALERT_RULES,
)

from typing import List, Dict
from dataclasses import dataclass


@dataclass
class AlertTemplate:
    name: str
    category: str
    severity: AlertSeverity
    message_template: str
    channels: List[str]
    cooldown_seconds: int = 300
    enabled: bool = True

__all__ = [
    "AlertSeverity",
    "AlertCategory",
    "AlertTemplate",
    "ALERT_SEVERITY_CONFIG",
    "ALERT_CATEGORIES",
    "TRADING_ALERT_RULES",
    "SYSTEM_ALERT_RULES",
    "PERFORMANCE_ALERT_RULES",
]