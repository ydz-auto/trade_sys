"""
Monitoring 配置 - 基础设施配置
"""

from infrastructure.config.enums import MonitoringCategory


MONITORING_CONFIGS = {
    "monitoring.metrics_collection_interval": 60,
    "monitoring.health_check_interval": 30,
    "monitoring.alert_check_interval": 10,
    "monitoring.cpu_percent_threshold": 90,
    "monitoring.memory_percent_threshold": 90,
    "monitoring.disk_percent_threshold": 85,
}


SYSTEM_HEALTH_METRICS = [
    "cpu_percent",
    "memory_percent",
    "disk_percent",
    "network_in",
    "network_out",
]

TRADING_PERFORMANCE_METRICS = [
    "balance",
    "pnl",
    "pnl_percent",
    "positions_count",
    "total_exposure",
    "trades_today",
    "wins_today",
    "losses_today",
]

RISK_METRICS = [
    "risk_index",
    "risk_level",
    "max_drawdown",
    "daily_loss",
    "consecutive_losses",
]
