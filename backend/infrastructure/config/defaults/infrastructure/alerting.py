"""
Alerting 配置 - 基础设施配置
"""

from infrastructure.config.enums import AlertSeverity, AlertCategory


ALERTING_CONFIGS = {
    "alerting.default_cooldown": 300,
    "alerting.telegram_enabled": False,
    "alerting.email_enabled": False,
    "alerting.slack_enabled": False,
    "alerting.sms_enabled": False,
}


ALERT_SEVERITY_CONFIG = {
    AlertSeverity.INFO: {
        "color": "blue",
        "sound": False,
        "channels": ["dashboard"],
        "auto_resolve": True,
    },
    AlertSeverity.WARNING: {
        "color": "yellow",
        "sound": True,
        "channels": ["dashboard", "telegram"],
        "auto_resolve": True,
    },
    AlertSeverity.ERROR: {
        "color": "red",
        "sound": True,
        "channels": ["dashboard", "telegram", "email"],
        "auto_resolve": False,
    },
    AlertSeverity.CRITICAL: {
        "color": "purple",
        "sound": True,
        "channels": ["dashboard", "telegram", "email", "sms"],
        "auto_resolve": False,
    },
}


ALERT_CATEGORIES = {
    "system": "系统告警",
    "trading": "交易告警",
    "risk": "风险告警",
    "performance": "性能告警",
    "security": "安全告警",
}


TRADING_ALERT_RULES = [
    {
        "name": "high_risk_index",
        "category": "risk",
        "condition": "risk_index > 80",
        "severity": "ERROR",
        "message": "Risk index exceeded 80, trading paused",
        "enabled": True,
    },
    {
        "name": "large_drawdown",
        "category": "risk",
        "condition": "drawdown > 0.08",
        "severity": "ERROR",
        "message": "Drawdown exceeded 8%",
        "enabled": True,
    },
    {
        "name": "daily_loss_limit",
        "category": "risk",
        "condition": "daily_loss > 0.05",
        "severity": "ERROR",
        "message": "Daily loss limit exceeded",
        "enabled": True,
    },
    {
        "name": "consecutive_losses",
        "category": "trading",
        "condition": "consecutive_losses >= 3",
        "severity": "WARNING",
        "message": "3+ consecutive losses detected",
        "enabled": True,
    },
    {
        "name": "position_limit",
        "category": "risk",
        "condition": "total_exposure > 0.6",
        "severity": "WARNING",
        "message": "Position limit exceeded",
        "enabled": True,
    },
]


SYSTEM_ALERT_RULES = [
    {
        "name": "service_down",
        "category": "system",
        "condition": "service.status == 'DOWN'",
        "severity": "CRITICAL",
        "message": "Service {service_name} is down",
        "enabled": True,
    },
    {
        "name": "service_degraded",
        "category": "system",
        "condition": "service.status == 'DEGRADED'",
        "severity": "WARNING",
        "message": "Service {service_name} is degraded",
        "enabled": True,
    },
    {
        "name": "disk_space_low",
        "category": "system",
        "condition": "disk_percent > 85",
        "severity": "WARNING",
        "message": "Disk space usage above 85%",
        "enabled": True,
    },
    {
        "name": "memory_high",
        "category": "system",
        "condition": "memory_percent > 90",
        "severity": "ERROR",
        "message": "Memory usage above 90%",
        "enabled": True,
    },
]


PERFORMANCE_ALERT_RULES = [
    {
        "name": "high_latency",
        "category": "performance",
        "condition": "latency_ms > 1000",
        "severity": "WARNING",
        "message": "Service latency exceeds 1000ms",
        "enabled": True,
    },
    {
        "name": "high_error_rate",
        "category": "performance",
        "condition": "error_rate > 0.05",
        "severity": "ERROR",
        "message": "Error rate exceeds 5%",
        "enabled": True,
    },
    {
        "name": "cache_hit_rate_low",
        "category": "performance",
        "condition": "cache_hit_rate < 0.8",
        "severity": "WARNING",
        "message": "Cache hit rate below 80%",
        "enabled": True,
    },
]


ALL_ALERT_RULES = (
    TRADING_ALERT_RULES
    + SYSTEM_ALERT_RULES
    + PERFORMANCE_ALERT_RULES
)
