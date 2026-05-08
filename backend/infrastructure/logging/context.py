"""
日志上下文管理
支持在日志中注入request_id、user_id等上下文信息
"""

import contextvars
from typing import Optional, Dict, Any
from datetime import datetime
import uuid


request_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "request_id", default=None
)
user_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "user_id", default=None
)
session_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "session_id", default=None
)


class LogContext:
    def __init__(self, request_id: Optional[str] = None, user_id: Optional[str] = None):
        self.request_id = request_id or f"req_{uuid.uuid4().hex[:12]}"
        self.user_id = user_id
        self.session_id = session_id_var.get()
        self.extra: Dict[str, Any] = {}

    def set_request_id(self, request_id: str) -> None:
        self.request_id = request_id
        request_id_var.set(request_id)

    def set_user_id(self, user_id: str) -> None:
        self.user_id = user_id
        user_id_var.set(user_id)

    def set_session_id(self, session_id: str) -> None:
        self.session_id = session_id
        session_id_var.set(session_id)

    def add_extra(self, key: str, value: Any) -> None:
        self.extra[key] = value

    def get_context(self) -> Dict[str, Any]:
        context = {
            "request_id": self.request_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        if self.user_id:
            context["user_id"] = self.user_id
        if self.session_id:
            context["session_id"] = self.session_id
        context.update(self.extra)
        return context

    def __enter__(self):
        request_id_var.set(self.request_id)
        if self.user_id:
            user_id_var.set(self.user_id)
        if self.session_id:
            session_id_var.set(self.session_id)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        request_id_var.set(None)
        user_id_var.set(None)
        session_id_var.set(None)
        return False


class RequestContext:
    def __init__(self, request_id: Optional[str] = None):
        self.request_id = request_id or f"req_{uuid.uuid4().hex[:12]}"
        self._token = None

    def __enter__(self):
        self._token = request_id_var.set(self.request_id)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._token:
            request_id_var.reset(self._token)
        return False


def get_request_id() -> Optional[str]:
    return request_id_var.get()


def get_user_id() -> Optional[str]:
    return user_id_var.get()