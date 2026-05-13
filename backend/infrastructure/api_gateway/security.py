"""
API 安全认证
"""

import hmac
import hashlib
import secrets
import os
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import jwt

from infrastructure.logging import get_logger
from infrastructure.api_gateway.config import PERMISSIONS
from infrastructure.api_gateway.exceptions import (
    AuthError,
    InvalidCredentialsError,
    TokenExpiredError,
    PermissionDeniedError,
)

logger = get_logger("infrastructure.api_gateway.security")


class APIKeyAuth:
    def __init__(
        self,
        db_client: Optional[Any] = None,
    ):
        self.db = db_client

    async def generate_api_key(self, user_id: str) -> Tuple[str, str]:
        api_key = f"ta_{secrets.token_hex(16)}"
        api_secret = secrets.token_hex(32)
        hashed_secret = hashlib.sha256(api_secret.encode()).hexdigest()

        if self.db:
            await self.db.execute(
                """
                INSERT INTO api_keys (user_id, api_key, api_secret, permissions, status)
                VALUES ($1, $2, $3, $4, 'active')
                """,
                user_id,
                api_key,
                hashed_secret,
                "{}",
            )

        return api_key, api_secret

    async def verify_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        if not self.db:
            # 生产环境必须配置数据库
            if os.getenv("ALLOW_DEFAULT_ADMIN", "false").lower() == "true":
                logger.warning("Using default admin access - DISABLE IN PRODUCTION!")
                return {"id": "default", "role": "admin"}
            raise InvalidCredentialsError("Database not configured")

        row = await self.db.fetchrow(
            """
            SELECT u.*, ak.permissions
            FROM api_keys ak
            JOIN users u ON ak.user_id = u.id
            WHERE ak.api_key = $1 AND ak.status = 'active'
            """,
            api_key,
        )

        if not row:
            raise InvalidCredentialsError("Invalid API key")

        return dict(row)

    async def revoke_api_key(self, api_key: str) -> bool:
        if not self.db:
            return True

        result = await self.db.execute(
            "UPDATE api_keys SET status = 'revoked' WHERE api_key = $1",
            api_key,
        )
        return "UPDATE 1" in result


class JWTAuth:
    def __init__(
        self,
        secret_key: Optional[str] = None,
        algorithm: str = "HS256",
        token_expiry_hours: int = 24,
    ):
        # 优先从环境变量读取密钥
        self.secret_key = secret_key or os.getenv("JWT_SECRET_KEY")
        
        if not self.secret_key:
            # 生产环境必须配置密钥
            if os.getenv("ENV") == "production":
                raise RuntimeError("JWT_SECRET_KEY must be configured in production")
                
            # 开发环境生成临时密钥
            self.secret_key = secrets.token_hex(64)
            logger.warning(
                "Using auto-generated JWT_SECRET_KEY - THIS WILL INVALIDATE ALL TOKENS ON RESTART!"
            )
        
        self.algorithm = algorithm
        self.token_expiry_hours = token_expiry_hours

    def create_token(
        self,
        user_id: str,
        role: str,
        additional_claims: Optional[Dict] = None,
    ) -> str:
        now = datetime.utcnow()
        payload = {
            "sub": user_id,
            "role": role,
            "iat": now,
            "exp": now + timedelta(hours=self.token_expiry_hours),
        }

        if additional_claims:
            payload.update(additional_claims)

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    async def verify_token(self, token: str) -> Dict[str, Any]:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            if "exp" in payload:
                exp = datetime.fromtimestamp(payload["exp"])
                if exp < datetime.utcnow():
                    raise TokenExpiredError()

            return {
                "user_id": payload.get("sub"),
                "role": payload.get("role"),
                "claims": {k: v for k, v in payload.items() if k not in ["sub", "role", "iat", "exp"]},
            }

        except jwt.ExpiredSignatureError:
            raise TokenExpiredError()
        except jwt.InvalidTokenError:
            raise AuthError("Invalid token")

    def decode_token_unsafe(self, token: str) -> Dict[str, Any]:
        try:
            return jwt.decode(token, options={"verify_signature": False})
        except Exception:
            return {}


class PermissionChecker:
    def __init__(self, permissions: Optional[Dict] = None):
        self.permissions = permissions or PERMISSIONS

    def has_permission(
        self,
        user_role: str,
        method: str,
        path: str,
    ) -> bool:
        role_permissions = self.permissions.get(user_role, [])

        if "*" in role_permissions:
            return True

        permission = f"{method} {path}"

        for perm in role_permissions:
            perm_pattern = perm.replace("*", ".*")
            perm_pattern = perm_pattern.replace("/", "\\/")

            if f"^{perm_pattern}$" == f"^{permission.replace('/', '\\/')}$":
                return True

            if perm.endswith("*") and permission.startswith(perm[:-1]):
                return True

        return False

    def check_permission(
        self,
        user_role: str,
        method: str,
        path: str,
    ) -> None:
        if not self.has_permission(user_role, method, path):
            raise PermissionDeniedError(f"Permission denied: {method} {path}")


class RequestSignature:
    @staticmethod
    def generate_signature(
        api_secret: str,
        method: str,
        path: str,
        body: str = "",
        timestamp: Optional[int] = None,
    ) -> str:
        timestamp = timestamp or int(datetime.utcnow().timestamp())

        message = f"{method}\n{path}\n{timestamp}\n{body}"

        signature = hmac.new(
            api_secret.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()

        return signature

    @staticmethod
    def verify_signature(
        api_secret: str,
        method: str,
        path: str,
        body: str,
        signature: str,
        timestamp: int,
        tolerance: int = 300,
    ) -> bool:
        current_time = int(datetime.utcnow().timestamp())

        if abs(current_time - timestamp) > tolerance:
            return False

        expected_signature = RequestSignature.generate_signature(
            api_secret, method, path, body, timestamp
        )

        return hmac.compare_digest(expected_signature, signature)