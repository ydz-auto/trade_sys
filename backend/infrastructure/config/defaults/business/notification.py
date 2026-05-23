"""
Notification 配置 - 业务配置
"""

NOTIFICATION_CONFIGS = {
    "notification.telegram_enabled": False,
    "notification.email_enabled": False,
    "notification.slack_enabled": False,
    "notification.alert_on_trade": True,
    "notification.alert_on_position": True,
    "notification.alert_on_risk": True,
}


NOTIFICATION_SCHEMAS = {
    "notification.telegram_enabled": {
        "value_type": "bool",
        "default": False,
        "description": "Enable Telegram notifications",
    },
    "notification.email_enabled": {
        "value_type": "bool",
        "default": False,
        "description": "Enable email notifications",
    },
    "notification.slack_enabled": {
        "value_type": "bool",
        "default": False,
        "description": "Enable Slack notifications",
    },
    "notification.alert_on_trade": {
        "value_type": "bool",
        "default": True,
        "description": "Alert on trade execution",
    },
    "notification.alert_on_position": {
        "value_type": "bool",
        "default": True,
        "description": "Alert on position changes",
    },
    "notification.alert_on_risk": {
        "value_type": "bool",
        "default": True,
        "description": "Alert on risk threshold breach",
    },
}
