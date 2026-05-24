"""
API 异常定义
"""

from typing import Optional


class APIError(Exception):
    def __init__(
        self,
        message: str,
        code: int = 1000,
        details: Optional[dict] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


class AuthError(APIError):
    def __init__(
        self,
        message: str = "Authentication error",
        code: int = 2000,
    ):
        super().__init__(message, code)


class InvalidCredentialsError(AuthError):
    def __init__(self, message: str = "Invalid credentials"):
        super().__init__(message, code=2001)


class TokenExpiredError(AuthError):
    def __init__(self, message: str = "Token expired"):
        super().__init__(message, code=2002)


class PermissionDeniedError(AuthError):
    def __init__(self, message: str = "Permission denied"):
        super().__init__(message, code=2003)


class ValidationError(APIError):
    def __init__(
        self,
        message: str = "Validation error",
        details: Optional[dict] = None,
    ):
        super().__init__(message, code=3001, details=details)


class MissingParameterError(ValidationError):
    def __init__(self, parameter: str):
        super().__init__(f"Missing required parameter: {parameter}", code=3002)


class InvalidParameterError(ValidationError):
    def __init__(self, parameter: str, reason: str):
        super().__init__(f"Invalid parameter: {parameter}", details={"parameter": parameter, "reason": reason}, code=3001)


class RateLimitError(APIError):
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message, code=5001)


class CircuitBreakerError(APIError):
    def __init__(self, message: str = "Circuit breaker triggered"):
        super().__init__(message, code=5002)


class ServiceUnavailableError(APIError):
    def __init__(self, message: str = "Service unavailable"):
        super().__init__(message, code=1001)


class ServiceTimeoutError(APIError):
    def __init__(self, message: str = "Service timeout"):
        super().__init__(message, code=1002)


class BusinessError(APIError):
    def __init__(self, message: str, code: int = 4000):
        super().__init__(message, code=code)


class RiskControlError(BusinessError):
    def __init__(self, message: str = "Risk control triggered"):
        super().__init__(message, code=4001)


class PositionLimitError(BusinessError):
    def __init__(self, message: str = "Position limit exceeded"):
        super().__init__(message, code=4002)


class InsufficientBalanceError(BusinessError):
    def __init__(self, message: str = "Insufficient balance"):
        super().__init__(message, code=4003)


class OrderFailedError(BusinessError):
    def __init__(self, message: str = "Order failed"):
        super().__init__(message, code=4004)