"""
日志记录器工厂
根据日志类型创建对应的日志记录器
"""

import os
import logging
from typing import Dict, Optional, Any
from pathlib import Path


from infrastructure.logging.config import (
    LogType,
    LogLevel,
    LOG_CONFIG,
    LOG_DIR,
)
from infrastructure.logging.formatters import (
    JSONFormatter,
    TextFormatter,
    TradeLogFormatter,
    SignalLogFormatter,
    AuditLogFormatter,
)
from infrastructure.logging.handlers import (
    FileHandler,
    RotatingFileHandler,
    ConsoleHandler,
    ElasticsearchHandler,
)
from infrastructure.logging.context import (
    LogContext,
    request_id_var,
    user_id_var,
    get_request_id,
    get_user_id,
)


class LoggerAdapter(logging.LoggerAdapter):
    def process(self, msg: str, kwargs: Dict) -> tuple:
        extra = kwargs.get("extra", {})

        request_id = get_request_id()
        if request_id:
            extra["request_id"] = request_id

        user_id = get_user_id()
        if user_id:
            extra["user_id"] = user_id

        kwargs["extra"] = extra
        return msg, kwargs


class LoggerFactory:
    _loggers: Dict[str, logging.Logger] = {}
    _initialized: bool = False

    _formatters = {
        LogType.TRADE: TradeLogFormatter(),
        LogType.SIGNAL: SignalLogFormatter(),
        LogType.AUDIT: AuditLogFormatter(),
        LogType.ERROR: JSONFormatter(),
        LogType.SYSTEM: JSONFormatter(),
        LogType.ACCESS: JSONFormatter(),
        LogType.PERFORMANCE: JSONFormatter(),
    }

    @classmethod
    def initialize(cls, log_dir: str = LOG_DIR, log_level: str = "INFO"):
        os.makedirs(log_dir, exist_ok=True)
        os.makedirs(os.path.join(log_dir, "archive"), exist_ok=True)
        os.makedirs(os.path.join(log_dir, "raw"), exist_ok=True)
        os.makedirs(os.path.join(log_dir, "processed"), exist_ok=True)

        cls._initialized = True

        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

        if not root_logger.handlers:
            console_handler = ConsoleHandler()
            console_handler.setFormatter(TextFormatter())
            root_logger.addHandler(console_handler)

    @classmethod
    def get_logger(
        cls,
        name: str,
        log_type: Optional[LogType] = None,
        level: Optional[str] = None,
    ) -> logging.Logger:
        if log_type and log_type in LOG_CONFIG:
            config = LOG_CONFIG[log_type]
            log_file = os.path.join(LOG_DIR, config["file"])
            return cls._create_file_logger(name, log_file, log_type, level)
        else:
            return cls._get_or_create_logger(name, level)

    @classmethod
    def _create_file_logger(
        cls,
        name: str,
        log_file: str,
        log_type: LogType,
        level: Optional[str] = None,
    ) -> logging.Logger:
        logger_name = f"{log_type.value}.{name}"
        if logger_name in cls._loggers:
            return cls._loggers[logger_name]

        logger = logging.getLogger(logger_name)
        logger.setLevel(
            getattr(logging, (level or LOG_CONFIG[log_type]["level"]).upper(), logging.INFO)
        )
        logger.propagate = False

        config = LOG_CONFIG[log_type]
        retention_days = config.get("retention", 30)

        file_handler = RotatingFileHandler(
            filename=log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=10,
            retention_days=retention_days,
        )
        file_handler.setFormatter(cls._formatters.get(log_type, JSONFormatter()))
        logger.addHandler(file_handler)

        if config.get("level") == LogLevel.ERROR or level == "ERROR":
            error_file = log_file.replace(".log", "_error.log")
            error_handler = FileHandler(
                filename=error_file,
                retention_days=retention_days,
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(JSONFormatter())
            logger.addHandler(error_handler)

        cls._loggers[logger_name] = logger
        return logger

    @classmethod
    def _get_or_create_logger(
        cls,
        name: str,
        level: Optional[str] = None,
    ) -> logging.Logger:
        if name in cls._loggers:
            return cls._loggers[name]

        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, (level or "INFO").upper(), logging.INFO))
        logger.propagate = False

        if not logger.handlers:
            console_handler = ConsoleHandler()
            console_handler.setFormatter(TextFormatter())
            logger.addHandler(console_handler)

        cls._loggers[name] = logger
        return logger

    @classmethod
    def get_trade_logger(cls, name: str = "execution_service") -> logging.Logger:
        return cls.get_logger(name, LogType.TRADE)

    @classmethod
    def get_signal_logger(cls, name: str = "decision_service") -> logging.Logger:
        return cls.get_logger(name, LogType.SIGNAL)

    @classmethod
    def get_error_logger(cls, name: str = "system") -> logging.Logger:
        return cls.get_logger(name, LogType.ERROR)

    @classmethod
    def get_audit_logger(cls, name: str = "audit_service") -> logging.Logger:
        return cls.get_logger(name, LogType.AUDIT)

    @classmethod
    def get_system_logger(cls, name: str = "system") -> logging.Logger:
        return cls.get_logger(name, LogType.SYSTEM)

    @classmethod
    def get_access_logger(cls, name: str = "api_gateway") -> logging.Logger:
        return cls.get_logger(name, LogType.ACCESS)

    @classmethod
    def get_performance_logger(cls, name: str = "performance") -> logging.Logger:
        return cls.get_logger(name, LogType.PERFORMANCE)

    @classmethod
    def add_elk_handler(
        cls,
        logger_name: str,
        es_host: str = "localhost",
        es_port: int = 9200,
    ):
        logger = cls._get_or_create_logger(logger_name)
        elk_handler = ElasticsearchHandler(es_host=es_host, es_port=es_port)
        elk_handler.setFormatter(JSONFormatter())
        logger.addHandler(elk_handler)


def get_logger(name: str) -> logging.Logger:
    return LoggerFactory._get_or_create_logger(name)


def get_trade_logger(name: str = "execution_service") -> logging.Logger:
    return LoggerFactory.get_trade_logger(name)


def get_signal_logger(name: str = "decision_service") -> logging.Logger:
    return LoggerFactory.get_signal_logger(name)


def get_error_logger(name: str = "system") -> logging.Logger:
    return LoggerFactory.get_error_logger(name)


def get_audit_logger(name: str = "audit_service") -> logging.Logger:
    return LoggerFactory.get_audit_logger(name)