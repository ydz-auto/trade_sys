"""
告警管理模块
"""

import time
import asyncio
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum


class AlertLevel(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


ALERT_LEVELS = {
    AlertLevel.INFO: {"color": "blue", "sound": False, "channels": ["dashboard"]},
    AlertLevel.WARNING: {
        "color": "yellow",
        "sound": True,
        "channels": ["dashboard", "telegram"],
    },
    AlertLevel.ERROR: {
        "color": "red",
        "sound": True,
        "channels": ["dashboard", "telegram", "email"],
    },
    AlertLevel.CRITICAL: {
        "color": "purple",
        "sound": True,
        "channels": ["dashboard", "telegram", "email", "sms"],
    },
}


@dataclass
class Alert:
    alert_id: str
    name: str
    level: AlertLevel
    message: str
    context: Dict[str, Any] = field(default_factory=dict)
    status: str = "ACTIVE"
    created_at: float = field(default_factory=time.time)
    resolved_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "name": self.name,
            "level": self.level.value,
            "message": self.message,
            "context": self.context,
            "status": self.status,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
        }


@dataclass
class AlertRule:
    name: str
    condition: str
    level: AlertLevel
    message: str
    enabled: bool = True

    def evaluate(self, context: Dict[str, Any]) -> bool:
        if not self.enabled:
            return False
        return self._evaluate_condition(self.condition, context)

    def _evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        try:
            local_vars = dict(context)
            return eval(condition, {"__builtins__": {}}, local_vars)
        except Exception:
            return False


class AlertChannel:
    async def send(self, alert: Alert):
        raise NotImplementedError


class DashboardChannel(AlertChannel):
    async def send(self, alert: Alert):
        pass


class TelegramChannel(AlertChannel):
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id

    async def send(self, alert: Alert):
        try:
            import httpx
            import json

            text = f"[{alert.level.value}] {alert.message}"
            if alert.context:
                text += f"\n\n{json.dumps(alert.context, indent=2)}"

            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            async with httpx.AsyncClient() as client:
                await client.post(
                    url,
                    json={
                        "chat_id": self.chat_id,
                        "text": text,
                        "parse_mode": "HTML",
                    },
                    timeout=10.0,
                )
        except Exception:
            pass


class EmailChannel(AlertChannel):
    def __init__(
        self,
        smtp_server: str,
        smtp_port: int,
        sender: str,
        recipients: List[str],
        password: str,
    ):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender = sender
        self.recipients = recipients
        self.password = password

    async def send(self, alert: Alert):
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            msg = MIMEMultipart()
            msg["From"] = self.sender
            msg["To"] = ", ".join(self.recipients)
            msg["Subject"] = f"[TradeAgent Alert] {alert.level.value}: {alert.message[:50]}"

            body = f"{alert.message}\n\nContext:\n{alert.context}"
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender, self.password)
                server.send_message(msg)
        except Exception:
            pass


class SMSChannel(AlertChannel):
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret

    async def send(self, alert: Alert):
        pass


class AlertSender:
    def __init__(self):
        self.channels: Dict[str, AlertChannel] = {
            "dashboard": DashboardChannel(),
        }

    def add_channel(self, name: str, channel: AlertChannel):
        self.channels[name] = channel

    def set_telegram(self, bot_token: str, chat_id: str):
        self.channels["telegram"] = TelegramChannel(bot_token, chat_id)

    def set_email(
        self,
        smtp_server: str,
        smtp_port: int,
        sender: str,
        recipients: List[str],
        password: str,
    ):
        self.channels["email"] = EmailChannel(
            smtp_server, smtp_port, sender, recipients, password
        )

    def set_sms(self, api_key: str, api_secret: str):
        self.channels["sms"] = SMSChannel(api_key, api_secret)

    async def send(self, level: AlertLevel, message: str, context: Optional[Dict] = None):
        channels = ALERT_LEVELS[level]["channels"]
        for channel_name in channels:
            if channel_name in self.channels:
                alert = Alert(
                    alert_id=f"alert_{int(time.time() * 1000)}",
                    name="",
                    level=level,
                    message=message,
                    context=context or {},
                )
                await self.channels[channel_name].send(alert)


class AlertManager:
    def __init__(self, alert_sender: Optional[AlertSender] = None):
        self.alert_sender = alert_sender or AlertSender()
        self.rules: List[AlertRule] = []
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self._on_alert_callback: Optional[Callable] = None

    def add_rule(self, rule: AlertRule):
        self.rules.append(rule)

    def remove_rule(self, name: str):
        self.rules = [r for r in self.rules if r.name != name]

    def set_alert_callback(self, callback: Callable):
        self._on_alert_callback = callback

    async def evaluate_rules(self, context: Dict[str, Any]):
        for rule in self.rules:
            if rule.evaluate(context):
                await self.create_alert(
                    name=rule.name,
                    level=rule.level,
                    message=rule.message,
                    context=context,
                )

    async def create_alert(
        self,
        name: str,
        level: AlertLevel,
        message: str,
        context: Optional[Dict] = None,
    ):
        alert_id = f"alert_{name}_{int(time.time() * 1000)}"

        if alert_id in self.active_alerts:
            return

        alert = Alert(
            alert_id=alert_id,
            name=name,
            level=level,
            message=message,
            context=context or {},
        )

        self.active_alerts[alert_id] = alert
        self.alert_history.append(alert)

        if len(self.alert_history) > 1000:
            self.alert_history = self.alert_history[-1000:]

        await self.alert_sender.send(level, message, context)

        if self._on_alert_callback:
            self._on_alert_callback(alert)

    async def resolve_alert(self, alert_id: str):
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.status = "RESOLVED"
            alert.resolved_at = time.time()
            del self.active_alerts[alert_id]

    async def resolve_alerts_by_name(self, name: str):
        to_resolve = [aid for aid, a in self.active_alerts.items() if a.name == name]
        for alert_id in to_resolve:
            await self.resolve_alert(alert_id)

    def get_active_alerts(self) -> List[Alert]:
        return list(self.active_alerts.values())

    def get_alert_history(
        self,
        level: Optional[AlertLevel] = None,
        limit: int = 100,
    ) -> List[Alert]:
        history = self.alert_history
        if level:
            history = [a for a in history if a.level == level]
        return history[-limit:]


_default_alert_manager = AlertManager()
_default_alert_sender = AlertSender()


def get_alert_manager() -> AlertManager:
    return _default_alert_manager


def get_alert_sender() -> AlertSender:
    return _default_alert_sender


async def send_alert(
    level: AlertLevel,
    message: str,
    context: Optional[Dict] = None,
):
    await _default_alert_sender.send(level, message, context)