"""
告警渠道实现
"""

from typing import Dict, List, Optional, Any
import asyncio

from infrastructure.alerting.sender import AlertChannel, Alert


class SlackChannel(AlertChannel):
    def __init__(
        self,
        webhook_url: str,
        channel: str = "#alerts",
        username: str = "TradeAgent Alert",
    ):
        self.webhook_url = webhook_url
        self.channel = channel
        self.username = username

    async def send(self, alert: Alert) -> bool:
        try:
            import httpx

            emoji = {
                "INFO": ":information_source:",
                "WARNING": ":warning:",
                "ERROR": ":rotating_light:",
                "CRITICAL": ":fire:",
            }

            payload = {
                "channel": self.channel,
                "username": self.username,
                "icon_emoji": emoji.get(alert.severity.value, ":bell:"),
                "attachments": [
                    {
                        "color": self._get_severity_color(alert.severity.value),
                        "title": f"[{alert.severity.value}] {alert.message}",
                        "fields": [
                            {"title": "Category", "value": alert.category, "short": True},
                            {"title": "Alert ID", "value": alert.alert_id, "short": True},
                        ],
                        "footer": "TradeAgent Alerting",
                        "ts": alert.created_at,
                    }
                ],
            }

            if alert.context:
                context_text = "\n".join(f"• {k}: {v}" for k, v in alert.context.items())
                payload["attachments"][0]["text"] = f"```\n{context_text}\n```"

            async with httpx.AsyncClient() as client:
                response = await client.post(self.webhook_url, json=payload, timeout=10.0)

            return response.status_code == 200

        except Exception as e:
            print(f"Slack send error: {e}")
            return False

    def _get_severity_color(self, severity: str) -> str:
        colors = {
            "INFO": "#36a64f",
            "WARNING": "#ff9800",
            "ERROR": "#f44336",
            "CRITICAL": "#9c27b0",
        }
        return colors.get(severity, "#808080")

    async def close(self):
        pass


class DiscordChannel(AlertChannel):
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def send(self, alert: Alert) -> bool:
        try:
            import httpx

            embed = {
                "title": f"[{alert.severity.value}] {alert.message}",
                "color": self._get_severity_color(alert.severity.value),
                "fields": [
                    {"name": "Category", "value": alert.category, "inline": True},
                    {"name": "Alert ID", "value": alert.alert_id, "inline": True},
                ],
                "timestamp": self._format_timestamp(alert.created_at),
            }

            if alert.context:
                context_text = "\n".join(f"`{k}`: {v}" for k, v in alert.context.items())
                embed["description"] = f"```\n{context_text}\n```"

            payload = {"embeds": [embed]}

            async with httpx.AsyncClient() as client:
                response = await client.post(self.webhook_url, json=payload, timeout=10.0)

            return response.status_code == 204

        except Exception as e:
            print(f"Discord send error: {e}")
            return False

    def _get_severity_color(self, severity: str) -> int:
        colors = {
            "INFO": 0x36A64F,
            "WARNING": 0xFF9800,
            "ERROR": 0xF44336,
            "CRITICAL": 0x9C27B0,
        }
        return colors.get(severity, 0x808080)

    def _format_timestamp(self, timestamp: float) -> str:
        from datetime import datetime
        return datetime.utcfromtimestamp(timestamp).isoformat()

    async def close(self):
        pass


class PushoverChannel(AlertChannel):
    def __init__(
        self,
        api_token: str,
        user_key: str,
        device: Optional[str] = None,
        sound: Optional[str] = None,
    ):
        self.api_token = api_token
        self.user_key = user_key
        self.device = device
        self.sound = sound

    async def send(self, alert: Alert) -> bool:
        try:
            import httpx

            priority = {
                "INFO": 0,
                "WARNING": 0,
                "ERROR": 1,
                "CRITICAL": 2,
            }.get(alert.severity.value, 0)

            payload = {
                "token": self.api_token,
                "user": self.user_key,
                "message": alert.message,
                "title": f"[{alert.severity.value}] {alert.name}",
                "priority": priority,
            }

            if self.device:
                payload["device"] = self.device

            if self.sound:
                payload["sound"] = self.sound

            if alert.context:
                payload["message"] += "\n\n" + "\n".join(
                    f"{k}: {v}" for k, v in alert.context.items()
                )

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.pushover.net/1/messages.json",
                    data=payload,
                    timeout=10.0,
                )

            return response.status_code == 200

        except Exception as e:
            print(f"Pushover send error: {e}")
            return False

    async def close(self):
        pass


class LineNotifyChannel(AlertChannel):
    def __init__(self, access_token: str):
        self.access_token = access_token

    async def send(self, alert: Alert) -> bool:
        try:
            import httpx

            emoji = {
                "INFO": "ℹ️",
                "WARNING": "⚠️",
                "ERROR": "🚨",
                "CRITICAL": "🚨🚨",
            }

            message = f"{emoji.get(alert.severity.value, '')} {alert.message}"

            if alert.context:
                message += "\n\n" + "\n".join(f"{k}: {v}" for k, v in alert.context.items())

            headers = {"Authorization": f"Bearer {self.access_token}"}
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.line.me/v2/message/broadcast",
                    headers=headers,
                    data={"message": message},
                    timeout=10.0,
                )

            return response.status_code == 200

        except Exception as e:
            print(f"Line notify send error: {e}")
            return False

    async def close(self):
        pass


class WeChatWorkChannel(AlertChannel):
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def send(self, alert: Alert) -> bool:
        try:
            import httpx

            msg_type = "text"
            content = f"[{alert.severity.value}] {alert.message}"

            if alert.context:
                content += "\n\n" + "\n".join(f"{k}: {v}" for k, v in alert.context.items())

            payload = {"msgtype": msg_type, "text": {"content": content}}

            async with httpx.AsyncClient() as client:
                response = await client.post(self.webhook_url, json=payload, timeout=10.0)

            return response.status_code == 200

        except Exception as e:
            print(f"WeChat Work send error: {e}")
            return False

    async def close(self):
        pass