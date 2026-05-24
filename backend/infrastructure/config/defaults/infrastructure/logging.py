"""
Logging 配置 - 基础设施配置
"""

from infrastructure.config.enums import LogType, LogLevel


LOGGING_CONFIGS = {
    "logging.dir": "logs",
    "logging.archive_dir": "logs/archive",
    "logging.raw_dir": "logs/raw",
    "logging.processed_dir": "logs/processed",
    "logging.default_level": "INFO",
    "logging.trade_level": "INFO",
    "logging.signal_level": "INFO",
    "logging.error_level": "ERROR",
    "logging.audit_level": "INFO",
    "logging.system_level": "INFO",
    "logging.access_level": "INFO",
    "logging.performance_level": "INFO",
}


LOG_CONFIG = {
    LogType.TRADE: {
        "name": "交易日志",
        "file": "logs/trades.log",
        "retention": 90,
    },
    LogType.SIGNAL: {
        "name": "信号日志",
        "file": "logs/signals.log",
        "retention": 30,
    },
    LogType.ERROR: {
        "name": "错误日志",
        "file": "logs/errors.log",
        "retention": 90,
    },
    LogType.AUDIT: {
        "name": "审计日志",
        "file": "logs/audit.log",
        "retention": 365,
    },
    LogType.SYSTEM: {
        "name": "系统日志",
        "file": "logs/system.log",
        "retention": 30,
    },
    LogType.ACCESS: {
        "name": "访问日志",
        "file": "logs/access.log",
        "retention": 30,
    },
    LogType.PERFORMANCE: {
        "name": "性能日志",
        "file": "logs/performance.log",
        "retention": 14,
    },
}


LOG_LEVELS = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}


LOG_FORMAT = {
    "timestamp": "ISO8601格式",
    "level": "INFO/WARNING/ERROR",
    "logger": "模块名",
    "message": "日志消息",
    "request_id": "请求ID",
    "user_id": "用户ID",
    "extra": {},
}
