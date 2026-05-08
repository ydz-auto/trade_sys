"""
API 网关配置
从 shared.config 导入
"""

from shared.config.enums import HTTPMethod
from shared.config.defaults.infrastructure import (
    API_GATEWAY_CONFIGS,
    API_ROUTES,
    RATE_LIMITS,
    PERMISSIONS,
    ERROR_CODES,
)

from typing import List
from dataclasses import dataclass


@dataclass
class GatewayConfig:
    host: str = API_GATEWAY_CONFIGS.get("api_gateway.host", "0.0.0.0")
    port: int = API_GATEWAY_CONFIGS.get("api_gateway.port", 8000)
    debug: bool = API_GATEWAY_CONFIGS.get("api_gateway.debug", False)
    service_timeout: float = API_GATEWAY_CONFIGS.get("api_gateway.service_timeout", 30.0)
    max_retries: int = API_GATEWAY_CONFIGS.get("api_gateway.max_retries", 3)
    rate_limit_enabled: bool = API_GATEWAY_CONFIGS.get("api_gateway.rate_limit_enabled", True)
    auth_enabled: bool = API_GATEWAY_CONFIGS.get("api_gateway.auth_enabled", True)
    log_requests: bool = API_GATEWAY_CONFIGS.get("api_gateway.log_requests", True)
    cors_enabled: bool = API_GATEWAY_CONFIGS.get("api_gateway.cors_enabled", True)
    allowed_origins: List[str] = None

    def __post_init__(self):
        if self.allowed_origins is None:
            self.allowed_origins = ["*"]

__all__ = [
    "HTTPMethod",
    "GatewayConfig",
    "API_ROUTES",
    "RATE_LIMITS",
    "PERMISSIONS",
    "ERROR_CODES",
]