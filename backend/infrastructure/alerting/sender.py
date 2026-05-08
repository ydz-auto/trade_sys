"""
告警发送器
"""

import time
import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

from infrastructure.alerting.config import AlertSeverity, ALERT_SEVERITY_CONFIG


@dataclass
class Alert:
    alert_id: str
    name: str
    severity: AlertSeverity
    message: str
    category: str
    context: Dict[str, Any] = field(default_factory=dict)
    channels: List[str] = field(default_factory=list)
    status: str = "ACTIVE"
    created_at: float = field(default_factory=time.time)
    resolved_at: Optional[float] = None
    acknowledged_at: Optional[float] = None
    acknowledged_by: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "name": self.name,
            "severity": self.severity.value,
            "message": self.message,
            "category": self.category,
            "context": self.context,
            "channels": self.channels,
            "status": self.status,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
            "acknowledged_at": self.acknowledged_at,
            "acknowledged_by": self.acknowledged_by,
        }


class AlertChannel(ABC):
    @abstractmethod
    async def send(self, alert: Alert) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def close(self):
        raise NotImplementedError


class TelegramChannel(AlertChannel):
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self._session = None

    async def send(self, alert: Alert) -> bool:
        try:
            import httpx

            emoji = {
                AlertSeverity.INFO: "ℹ️",
                AlertSeverity.WARNING: "⚠️",
                AlertSeverity.ERROR: "🚨",
                AlertSeverity.CRITICAL: "🚨🚨",
            }

            text = f"{emoji.get(alert.severity, '')} [{alert.severity.value}] {alert.message}"

            if alert.context:
                text += f"\n\n```\n{self._format_context(alert.context)}\n```"

            text += f"\n\n🕐 {self._format_time(alert.created_at)}"

            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json={
                        "chat_id": self.chat_id,
                        "text": text,
                        "parse_mode": "Markdown",
                    },
                    timeout=10.0,
                )

            return response.status_code == 200

        except Exception as e:
            print(f"Telegram send error: {e}")
            return False

    def _format_context(self, context: Dict) -> str:
        lines = []
        for k, v in context.items():
            lines.append(f"{k}: {v}")
        return "\n".join(lines)

    def _format_time(self, timestamp: float) -> str:
        from datetime import datetime
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    async def close(self):
        pass


class EmailChannel(AlertChannel):
    def __init__(
        self,
        smtp_server: str,
        smtp_port: int,
        sender: str,
        recipients: List[str],
        password: str,
        use_tls: bool = True,
    ):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender = sender
        self.recipients = recipients
        self.password = password
        self.use_tls = use_tls

    async def send(self, alert: Alert) -> bool:
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            msg = MIMEMultipart()
            msg["From"] = self.sender
            msg["To"] = ", ".join(self.recipients)
            msg["Subject"] = f"[{alert.severity.value}] {alert.message[:100]}"

            html = f"""
            <html>
            <body>
            <h2>{alert.message}</h2>
            <p><strong>Severity:</strong> {alert.severity.value}</p>
            <p><strong>Category:</strong> {alert.category}</p>
            <p><strong>Time:</strong> {self._format_time(alert.created_at)}</p>
            <h3>Context:</h3>
            <pre>{self._format_context(alert.context)}</pre>
            </body>
            </html>
            """

            msg.attach(MIMEText(html, "html"))

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.sender, self.password)
                server.send_message(msg)

            return True

        except Exception as e:
            print(f"Email send error: {e}")
            return False

    def _format_context(self, context: Dict) -> str:
        return "\n".join(f"{k}: {v}" for k, v in context.items())

    def _format_time(self, timestamp: float) -> str:
        from datetime import datetime
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    async def close(self):
        pass


class SMSChannel(AlertChannel):
    def __init__(self, api_key: str, api_secret: str, sender: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.sender = sender

    async def send(self, alert: Alert) -> bool:
        try:
            import httpx

            message = f"[{alert.severity.value}] {alert.message[:160]}"

            url = "https://api.smsprovider.com/send"
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json={
                        "api_key": self.api_key,
                        "api_secret": self.api_secret,
                        "sender": self.sender,
                        "message": message,
                    },
                    timeout=10.0,
                )

            return response.status_code == 200

        except Exception as e:
            print(f"SMS send error: {e}")
            return False

    async def close(self):
        pass


class WebhookChannel(AlertChannel):
    def __init__(self, url: str, headers: Optional[Dict[str, str]] = None):
        self.url = url
        self.headers = headers or {}
        self._session = None

    async def send(self, alert: Alert) -> bool:
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.url,
                    json=alert.to_dict(),
                    headers=self.headers,
                    timeout=10.0,
                )

            return response.status_code == 200

        except Exception as e:
            print(f"Webhook send error: {e}")
            return False

    async def close(self):
        pass


class DashboardChannel(AlertChannel):
    async def send(self, alert: Alert) -> bool:
        return True

    async def close(self):
        pass


class AlertSender:
    def __init__(self):
        self.channels: Dict[str, AlertChannel] = {
            "dashboard": DashboardChannel(),
        }
        self._alert_history: List[Alert] = []
        self._max_history = 1000

    def add_channel(self, name: str, channel: AlertChannel):
        self.channels[name] = channel

    def remove_channel(self, name: str):
        if name in self.channels and name != "dashboard":
            del self.channels[name]

    async def send_alert(
        self,
        alert: Alert,
        channels: Optional[List[str]] = None,
    ) -> Dict[str, bool]:
        if channels is None:
            severity_config = ALERT_SEVERITY_CONFIG.get(alert.severity, {})
            channels = severity_config.get("channels", ["dashboard"])

        results = {}

        for channel_name in channels:
            if channel_name in self.channels:
                channel = self.channels[channel_name]
                try:
                    results[channel_name] = await channel.send(alert)
                except Exception as e:
                    print(f"Error sending to {channel_name}: {e}")
                    results[channel_name] = False
            else:
                results[channel_name] = False

        self._alert_history.append(alert)
        if len(self._alert_history) > self._max_history:
            self._alert_history = self._alert_history[-self._max_history :]

        return results

    async def send(
        self,
        severity: AlertSeverity,
        message: str,
        name: str = "",
        category: str = "general",
        context: Optional[Dict] = None,
    ) -> Alert:
        alert = Alert(
            alert_id=f"alert_{int(time.time() * 1000)}",
            name=name,
            severity=severity,
            message=message,
            category=category,
            context=context or {},
        )

        await self.send_alert(alert)

        return alert

    def get_history(self, limit: int = 100) -> List[Alert]:
        return self._alert_history[-limit:]


_default_alert_sender: Optional[AlertSender] = None


def get_alert_sender() -> AlertSender:
    global _default_alert_sender
    if _default_alert_sender is None:
        _default_alert_sender = AlertSender()
    return _default_alert_sender