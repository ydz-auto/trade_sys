"""
TradeAgent API Gateway Module
API 网关模块
"""

from infrastructure.api_gateway.router import Router, Route
from infrastructure.api_gateway.middleware import (
    AuthMiddleware,
    RateLimitMiddleware,
    CORSMiddleware,
    RequestLoggerMiddleware,
    ErrorHandlerMiddleware,
)
from infrastructure.api_gateway.response import Response, APIResponse
from infrastructure.api_gateway.exceptions import (
    APIError,
    AuthError,
    ValidationError,
    RateLimitError,
)
from infrastructure.api_gateway.security import (
    APIKeyAuth,
    JWTAuth,
    PermissionChecker,
)

__all__ = [
    "Router",
    "Route",
    "AuthMiddleware",
    "RateLimitMiddleware",
    "CORSMiddleware",
    "RequestLoggerMiddleware",
    "ErrorHandlerMiddleware",
    "Response",
    "APIResponse",
    "APIError",
    "AuthError",
    "ValidationError",
    "RateLimitError",
    "APIKeyAuth",
    "JWTAuth",
    "PermissionChecker",
]