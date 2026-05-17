"""
日志格式化器
支持JSON和文本两种格式
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta
import os

TZ_OFFSET_HOURS = int(os.getenv("TZ_OFFSET_HOURS", "8"))


def get_local_time() -> datetime:
    """获取本地时间（默认东八区）"""
    utc_now = datetime.utcnow()
    return utc_now.replace(tzinfo=timezone.utc).astimezone(
        timezone(timedelta(hours=TZ_OFFSET_HOURS))
    )


class BaseFormatter(logging.Formatter):
    def __init__(self, fmt: Optional[str] = None):
        super().__init__(fmt)

    def format(self, record: logging.LogRecord) -> str:
        log_data = self._build_log_data(record)
        return self._format_message(log_data)

    def _build_log_data(self, record: logging.LogRecord) -> Dict[str, Any]:
        raise NotImplementedError

    def _format_message(self, log_data: Dict[str, Any]) -> str:
        raise NotImplementedError


class JSONFormatter(BaseFormatter):
    def __init__(
        self,
        include_extra: bool = True,
        include_fields: Optional[list] = None,
    ):
        super().__init__()
        self.include_extra = include_extra
        self.include_fields = include_fields or []

    def _build_log_data(self, record: logging.LogRecord) -> Dict[str, Any]:
        log_data = {
            "timestamp": get_local_time().strftime("%Y-%m-%d %H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if hasattr(record, "request_id") and record.request_id:
            log_data["request_id"] = record.request_id
        if hasattr(record, "user_id") and record.user_id:
            log_data["user_id"] = record.user_id

        if self.include_extra:
            extra_fields = [
                "symbol",
                "order_id",
                "signal_id",
                "action",
                "side",
                "size",
                "price",
                "filled_price",
                "commission",
                "status",
                "strategy",
                "confidence",
                "risk_index",
            ]
            for field in extra_fields:
                if hasattr(record, field):
                    log_data[field] = getattr(record, field)

        if hasattr(record, "extra_data") and record.extra_data:
            log_data["extra"] = record.extra_data

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        for field in self.include_fields:
            if hasattr(record, field):
                log_data[field] = getattr(record, field)

        return log_data

    def _format_message(self, log_data: Dict[str, Any]) -> str:
        return json.dumps(log_data, default=str, ensure_ascii=False)


class TextFormatter(BaseFormatter):
    def __init__(
        self,
        fmt: Optional[str] = None,
        include_extra: bool = True,
    ):
        default_fmt = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
        super().__init__(fmt or default_fmt)
        self.include_extra = include_extra

    def _build_log_data(self, record: logging.LogRecord) -> Dict[str, Any]:
        log_parts = []

        local_time = datetime.utcfromtimestamp(record.created).replace(
            tzinfo=timezone.utc
        ).astimezone(timezone(timedelta(hours=TZ_OFFSET_HOURS)))
        timestamp = local_time.strftime("%Y-%m-%d %H:%M:%S")
        log_parts.append(timestamp)

        log_parts.append(record.levelname)

        log_parts.append(f"[{record.name}]")

        log_parts.append(record.getMessage())

        extra_parts = []
        if hasattr(record, "request_id") and record.request_id:
            extra_parts.append(f"request_id={record.request_id}")
        if hasattr(record, "user_id") and record.user_id:
            extra_parts.append(f"user_id={record.user_id}")

        if self.include_extra:
            extra_fields = [
                "symbol",
                "order_id",
                "signal_id",
                "action",
                "side",
                "size",
                "price",
            ]
            for field in extra_fields:
                if hasattr(record, field) and getattr(record, field):
                    extra_parts.append(f"{field}={getattr(record, field)}")

        if extra_parts:
            log_parts.append("| " + " | ".join(extra_parts))

        return {"message": " ".join(log_parts)}

    def _format_message(self, log_data: Dict[str, Any]) -> str:
        return log_data.get("message", "")


class TradeLogFormatter(JSONFormatter):
    TRADE_FIELDS = [
        "order_id",
        "symbol",
        "action",
        "side",
        "size",
        "price",
        "filled_price",
        "commission",
        "status",
        "strategy",
        "signal_id",
        "confidence",
        "risk_index",
        "mode",
    ]

    def _build_log_data(self, record: logging.LogRecord) -> Dict[str, Any]:
        log_data = super()._build_log_data(record)

        for field in self.TRADE_FIELDS:
            if hasattr(record, field):
                log_data[field] = getattr(record, field)

        return log_data


class SignalLogFormatter(JSONFormatter):
    SIGNAL_FIELDS = [
        "signal_id",
        "symbol",
        "signal",
        "confidence",
        "composite_score",
        "regime",
        "factors",
        "risk_index",
        "position_size",
        "leverage",
        "action",
    ]

    def _build_log_data(self, record: logging.LogRecord) -> Dict[str, Any]:
        log_data = super()._build_log_data(record)

        for field in self.SIGNAL_FIELDS:
            if hasattr(record, field):
                log_data[field] = getattr(record, field)

        return log_data


class AuditLogFormatter(JSONFormatter):
    AUDIT_FIELDS = [
        "user_id",
        "action",
        "resource",
        "resource_id",
        "changes",
        "ip_address",
        "user_agent",
        "result",
    ]

    def _build_log_data(self, record: logging.LogRecord) -> Dict[str, Any]:
        log_data = super()._build_log_data(record)

        for field in self.AUDIT_FIELDS:
            if hasattr(record, field):
                log_data[field] = getattr(record, field)

        return log_data