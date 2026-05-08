"""
API 网关中间件
"""

import time
import uuid
import fnmatch
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass

from infrastructure.api_gateway.config import PERMISSIONS, RATE_LIMITS
from infrastructure.api_gateway.exceptions import (
    AuthError,
    RateLimitError,
    ValidationError,
)


@dataclass
class Request:
    method: str
    path: str
    headers: Dict[str, str]
    query_params: Dict[str, str]
    path_params: Dict[str, str]
    body: Optional[bytes] = None
    json_data: Optional[Dict] = None


@dataclass
class Response:
    status_code: int
    body: Any
    headers: Dict[str, str]


MiddlewareFunc = Callable[[Request], Optional[Response]]


class BaseMiddleware:
    async def __call__(self, request: Request) -> Optional[Response]:
        raise NotImplementedError


class AuthMiddleware(BaseMiddleware):
    def __init__(
        self,
        auth_service: Optional[Any] = None,
        public_paths: Optional[List[str]] = None,
    ):
        self.auth_service = auth_service
        self.public_paths = public_paths or [
            "/api/v1/system/health",
            "/api/v1/auth/login",
            "/api/v1/auth/register",
        ]

    async def __call__(self, request: Request) -> Optional[Response]:
        if request.path in self.public_paths:
            return None

        if not self.auth_service:
            return None

        auth_header = request.headers.get("Authorization")
        api_key = request.headers.get("X-API-Key")

        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
            try:
                user = await self.auth_service.verify_token(token)
                request.user = user
            except Exception as e:
                raise AuthError("Invalid token")
        elif api_key:
            try:
                user = await self.auth_service.verify_api_key(api_key)
                request.user = user
            except Exception as e:
                raise AuthError("Invalid API key")
        else:
            raise AuthError("Missing authentication")

        return None


class PermissionMiddleware(BaseMiddleware):
    def __init__(self, permission_checker: Optional[Any] = None):
        self.permission_checker = permission_checker

    async def __call__(self, request: Request) -> Optional[Response]:
        if not hasattr(request, "user") or not request.user:
            return None

        if not self.permission_checker:
            return None

        user_role = request.user.get("role", "viewer")

        if not self.permission_checker.has_permission(user_role, request.method, request.path):
            raise AuthError("Permission denied")

        return None


class RateLimitMiddleware(BaseMiddleware):
    def __init__(
        self,
        redis_client: Optional[Any] = None,
        rate_limits: Optional[Dict] = None,
    ):
        self.redis = redis_client
        self.rate_limits = rate_limits or RATE_LIMITS

    async def __call__(self, request: Request) -> Optional[Response]:
        if not self.redis:
            return None

        user_id = getattr(request, "user_id", request.headers.get("X-User-ID", "anonymous"))
        endpoint = getattr(request, "endpoint", "default")

        limit_config = self.rate_limits.get(endpoint, self.rate_limits["default"])

        key = f"rate_limit:{user_id}:{endpoint}"

        try:
            current = await self.redis.incr(key)

            if current == 1:
                await self.redis.expire(key, limit_config["window"])

            if current > limit_config["requests"]:
                raise RateLimitError(
                    f"Rate limit exceeded. Limit: {limit_config['requests']} per {limit_config['window']}s"
                )
        except RateLimitError:
            raise
        except Exception:
            pass

        return None


class CORSMiddleware(BaseMiddleware):
    def __init__(
        self,
        allowed_origins: Optional[List[str]] = None,
        allowed_methods: Optional[List[str]] = None,
        allowed_headers: Optional[List[str]] = None,
        allow_credentials: bool = True,
        max_age: int = 86400,
    ):
        self.allowed_origins = allowed_origins or ["*"]
        self.allowed_methods = allowed_methods or ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
        self.allowed_headers = allowed_headers or ["*"]
        self.allow_credentials = allow_credentials
        self.max_age = max_age

    async def __call__(self, request: Request) -> Optional[Response]:
        if request.method == "OPTIONS":
            origin = request.headers.get("Origin", "*")

            if self._is_origin_allowed(origin):
                headers = {
                    "Access-Control-Allow-Origin": origin,
                    "Access-Control-Allow-Methods": ", ".join(self.allowed_methods),
                    "Access-Control-Allow-Headers": ", ".join(self.allowed_headers),
                    "Access-Control-Max-Age": str(self.max_age),
                }

                if self.allow_credentials:
                    headers["Access-Control-Allow-Credentials"] = "true"

                return Response(200, "", headers)

        return None

    def _is_origin_allowed(self, origin: str) -> bool:
        if "*" in self.allowed_origins:
            return True
        return origin in self.allowed_origins


class RequestLoggerMiddleware(BaseMiddleware):
    def __init__(
        self,
        logger: Optional[Any] = None,
    ):
        self.logger = logger

    async def __call__(self, request: Request) -> Optional[Response]:
        request_id = f"req_{uuid.uuid4().hex[:12]}"
        request.request_id = request_id
        request.start_time = time.time()

        if self.logger:
            self.logger.info({
                "request_id": request_id,
                "method": request.method,
                "path": request.path,
            })

        return None


class ErrorHandlerMiddleware(BaseMiddleware):
    def __init__(
        self,
        error_handlers: Optional[Dict[type, Callable]] = None,
    ):
        self.error_handlers = error_handlers or {}

    async def __call__(self, request: Request) -> Optional[Response]:
        return None

    def handle_error(self, error: Exception) -> Response:
        error_type = type(error)

        if error_type in self.error_handlers:
            return self.error_handlers[error_type](error)

        if isinstance(error, AuthError):
            return Response(401, {"error": str(error)}, {})
        elif isinstance(error, ValidationError):
            return Response(400, {"error": str(error)}, {})
        elif isinstance(error, RateLimitError):
            return Response(429, {"error": str(error)}, {})
        else:
            return Response(500, {"error": "Internal server error"}, {})


class MiddlewareChain:
    def __init__(self, middlewares: List[BaseMiddleware]):
        self.middlewares = middlewares

    async def execute(self, request: Request) -> Optional[Response]:
        for middleware in self.middlewares:
            response = await middleware(request)
            if response:
                return response
        return None

    def add(self, middleware: BaseMiddleware):
        self.middlewares.append(middleware)