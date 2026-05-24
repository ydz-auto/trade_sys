"""
Config 枚举类型定义
"""

from enum import Enum


class ConfigCategory(str, Enum):
    SYSTEM = "system"
    TRADING = "trading"
    RISK = "risk"
    STRATEGY = "strategy"
    MARKET = "market"
    NOTIFICATION = "notification"
    DATABASE = "database"
    CACHE = "cache"
    API = "api"
    LOGGING = "logging"
    DATASOURCE = "datasource"
    MONITORING = "monitoring"
    ALERTING = "alerting"
    MIDDLEWARE = "middleware"
    API_GATEWAY = "api_gateway"
    APPROVAL = "approval"


class ConfigScope(str, Enum):
    GLOBAL = "GLOBAL"
    USER = "USER"
    STRATEGY = "STRATEGY"


class DataSourceCategory(str, Enum):
    EXCHANGE = "exchange"
    NEWS = "news"
    MACRO = "macro"
    SOCIAL = "social"


class LogType(str, Enum):
    TRADE = "trade"
    SIGNAL = "signal"
    ERROR = "error"
    AUDIT = "audit"
    SYSTEM = "system"
    ACCESS = "access"
    PERFORMANCE = "performance"


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AlertSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AlertCategory(str, Enum):
    SYSTEM = "system"
    TRADING = "trading"
    RISK = "risk"
    PERFORMANCE = "performance"
    SECURITY = "security"


class MonitoringCategory(str, Enum):
    SYSTEM = "system"
    TRADING = "trading"
    RISK = "risk"


class ServiceStatus(str, Enum):
    OK = "OK"
    DEGRADED = "DEGRADED"
    DOWN = "DOWN"
    UNKNOWN = "UNKNOWN"


class CacheStrategy(str, Enum):
    WRITE_THROUGH = "write_through"
    WRITE_BEHIND = "write_behind"
    READ_ASIDE = "read_aside"
    CACHE_ASIDE = "cache_aside"


class HTTPMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    OPTIONS = "OPTIONS"