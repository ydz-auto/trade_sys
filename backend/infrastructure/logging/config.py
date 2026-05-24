"""
日志配置和常量定义
从 shared.config 导入
"""

from infrastructure.config.enums import LogType, LogLevel
from infrastructure.config.defaults.infrastructure import (
    LOGGING_CONFIGS,
    LOG_CONFIG,
    LOG_LEVELS,
    LOG_FORMAT,
)

LOG_DIR = LOGGING_CONFIGS.get("logging.dir", "logs")
LOG_ARCHIVE_DIR = LOGGING_CONFIGS.get("logging.archive_dir", "logs/archive")
LOG_RAW_DIR = LOGGING_CONFIGS.get("logging.raw_dir", "logs/raw")
LOG_PROCESSED_DIR = LOGGING_CONFIGS.get("logging.processed_dir", "logs/processed")

__all__ = [
    "LogType",
    "LogLevel",
    "LOG_CONFIG",
    "LOG_LEVELS",
    "LOG_FORMAT",
    "LOG_DIR",
    "LOG_ARCHIVE_DIR",
    "LOG_RAW_DIR",
    "LOG_PROCESSED_DIR",
]