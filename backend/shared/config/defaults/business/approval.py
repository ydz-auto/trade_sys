"""
Approval Service Config - HITL 审批服务配置
"""

from typing import Dict, Any
from shared.config.enums import ConfigCategory, ConfigScope
from shared.config.schemas import ConfigSchema

# ============ 默认配置 ============

TRADING_MODE_DEFAULT = "hybrid"
TIMEOUT_SECONDS_DEFAULT = 300
MAX_RETRIES_DEFAULT = 2
RECALCULATE_ON_TIMEOUT_DEFAULT = True
SIGNAL_EXPIRES_SECONDS_DEFAULT = 60
DELAYED_THRESHOLD_SECONDS_DEFAULT = 60
PRICE_CHANGE_THRESHOLD_DEFAULT = 0.01
AUTO_THRESHOLD_USD_DEFAULT = 100
NOTIFY_TELEGRAM_DEFAULT = True
NOTIFY_WECHAT_DEFAULT = False
NOTIFY_SMS_DEFAULT = False
HIGH_RISK_THRESHOLD_DEFAULT = 0.7
NEW_SIGNAL_EXPIRES_SECONDS_DEFAULT = 30


# ============ 配置项定义 ============

APPROVAL_CONFIGS: Dict[str, Any] = {
    # 基础配置
    "approval.mode": TRADING_MODE_DEFAULT,
    "approval.timeout_seconds": TIMEOUT_SECONDS_DEFAULT,
    "approval.max_retries": MAX_RETRIES_DEFAULT,
    "approval.recalculate_on_timeout": RECALCULATE_ON_TIMEOUT_DEFAULT,
    
    # 信号时效性配置
    "approval.signal_expires_seconds": SIGNAL_EXPIRES_SECONDS_DEFAULT,
    "approval.delayed_threshold_seconds": DELAYED_THRESHOLD_SECONDS_DEFAULT,
    "approval.price_change_threshold": PRICE_CHANGE_THRESHOLD_DEFAULT,
    "approval.new_signal_expires_seconds": NEW_SIGNAL_EXPIRES_SECONDS_DEFAULT,
    
    # 自动批准配置
    "approval.auto_threshold_usd": AUTO_THRESHOLD_USD_DEFAULT,
    "approval.high_risk_threshold": HIGH_RISK_THRESHOLD_DEFAULT,
    
    # 通知渠道配置
    "approval.notify_telegram": NOTIFY_TELEGRAM_DEFAULT,
    "approval.notify_wechat": NOTIFY_WECHAT_DEFAULT,
    "approval.notify_sms": NOTIFY_SMS_DEFAULT,
    
    # Telegram 配置
    "approval.telegram.bot_token": "",
    "approval.telegram.approved_chat_ids": "",
    "approval.telegram.parse_mode": "HTML",
    
    # WeChat 配置
    "approval.wechat.webhook_url": "",
    "approval.wechat.corp_id": "",
    "approval.wechat.corp_secret": "",
    
    # 数据库配置
    "approval.storage.enabled": True,
    "approval.storage.ttl_days": 90,
    
    # SSE 配置
    "approval.sse.enabled": True,
    "approval.sse.heartbeat_interval": 30,
}


# ============ 配置 Schema ============

APPROVAL_SCHEMAS: Dict[str, Dict] = {
    "approval.mode": {
        "type": "string",
        "enum": ["auto", "manual", "hybrid"],
        "default": TRADING_MODE_DEFAULT,
        "description": "审批模式: auto=自动执行, manual=人工审批, hybrid=智能判断",
        "category": "approval",
        "scope": "system",
    },
    "approval.timeout_seconds": {
        "type": "integer",
        "minimum": 60,
        "maximum": 3600,
        "default": TIMEOUT_SECONDS_DEFAULT,
        "description": "审批超时时间（秒），超时后将触发重新计算",
        "category": "approval",
        "scope": "system",
    },
    "approval.max_retries": {
        "type": "integer",
        "minimum": 0,
        "maximum": 5,
        "default": MAX_RETRIES_DEFAULT,
        "description": "最大重新计算重试次数",
        "category": "approval",
        "scope": "system",
    },
    "approval.recalculate_on_timeout": {
        "type": "boolean",
        "default": RECALCULATE_ON_TIMEOUT_DEFAULT,
        "description": "超时后是否自动重新计算",
        "category": "approval",
        "scope": "system",
    },
    "approval.signal_expires_seconds": {
        "type": "integer",
        "minimum": 10,
        "maximum": 300,
        "default": SIGNAL_EXPIRES_SECONDS_DEFAULT,
        "description": "信号有效期（秒），超过此时间信号将被视为过期",
        "category": "approval",
        "scope": "system",
    },
    "approval.delayed_threshold_seconds": {
        "type": "integer",
        "minimum": 10,
        "maximum": 600,
        "default": DELAYED_THRESHOLD_SECONDS_DEFAULT,
        "description": "审批延迟阈值（秒），超过此时间需要重新验证价格",
        "category": "approval",
        "scope": "system",
    },
    "approval.price_change_threshold": {
        "type": "number",
        "minimum": 0.001,
        "maximum": 0.1,
        "default": PRICE_CHANGE_THRESHOLD_DEFAULT,
        "description": "价格变化阈值，超过此比例需要重新计算",
        "category": "approval",
        "scope": "system",
    },
    "approval.new_signal_expires_seconds": {
        "type": "integer",
        "minimum": 10,
        "maximum": 120,
        "default": NEW_SIGNAL_EXPIRES_SECONDS_DEFAULT,
        "description": "重新计算后新信号的有效期（秒），通常比原信号更短",
        "category": "approval",
        "scope": "system",
    },
    "approval.auto_threshold_usd": {
        "type": "number",
        "minimum": 0,
        "maximum": 10000,
        "default": AUTO_THRESHOLD_USD_DEFAULT,
        "description": "小额自动批准阈值（美元），低于此金额自动批准",
        "category": "approval",
        "scope": "system",
    },
    "approval.high_risk_threshold": {
        "type": "number",
        "minimum": 0,
        "maximum": 1,
        "default": HIGH_RISK_THRESHOLD_DEFAULT,
        "description": "高风险置信度阈值，低于此置信度需要人工确认",
        "category": "approval",
        "scope": "system",
    },
    "approval.notify_telegram": {
        "type": "boolean",
        "default": NOTIFY_TELEGRAM_DEFAULT,
        "description": "是否启用 Telegram 通知",
        "category": "approval",
        "scope": "system",
    },
    "approval.notify_wechat": {
        "type": "boolean",
        "default": NOTIFY_WECHAT_DEFAULT,
        "description": "是否启用 WeChat 通知",
        "category": "approval",
        "scope": "system",
    },
    "approval.notify_sms": {
        "type": "boolean",
        "default": NOTIFY_SMS_DEFAULT,
        "description": "是否启用 SMS 通知",
        "category": "approval",
        "scope": "system",
    },
    "approval.telegram.bot_token": {
        "type": "string",
        "default": "",
        "description": "Telegram Bot Token",
        "category": "approval",
        "scope": "system",
        "secret": True,
    },
    "approval.telegram.approved_chat_ids": {
        "type": "string",
        "default": "",
        "description": "Telegram 授权的 Chat ID（多个用逗号分隔）",
        "category": "approval",
        "scope": "system",
    },
    "approval.telegram.parse_mode": {
        "type": "string",
        "enum": ["HTML", "Markdown", "None"],
        "default": "HTML",
        "description": "Telegram 消息解析模式",
        "category": "approval",
        "scope": "system",
    },
    "approval.wechat.webhook_url": {
        "type": "string",
        "default": "",
        "description": "WeChat Webhook URL",
        "category": "approval",
        "scope": "system",
        "secret": True,
    },
    "approval.wechat.corp_id": {
        "type": "string",
        "default": "",
        "description": "企业微信 Corp ID",
        "category": "approval",
        "scope": "system",
    },
    "approval.wechat.corp_secret": {
        "type": "string",
        "default": "",
        "description": "企业微信 Corp Secret",
        "category": "approval",
        "scope": "system",
        "secret": True,
    },
    "approval.storage.enabled": {
        "type": "boolean",
        "default": True,
        "description": "是否启用审批记录存储",
        "category": "approval",
        "scope": "system",
    },
    "approval.storage.ttl_days": {
        "type": "integer",
        "minimum": 1,
        "maximum": 365,
        "default": 90,
        "description": "审批记录保留天数",
        "category": "approval",
        "scope": "system",
    },
    "approval.sse.enabled": {
        "type": "boolean",
        "default": True,
        "description": "是否启用 SSE 实时推送",
        "category": "approval",
        "scope": "system",
    },
    "approval.sse.heartbeat_interval": {
        "type": "integer",
        "minimum": 10,
        "maximum": 60,
        "default": 30,
        "description": "SSE 心跳间隔（秒）",
        "category": "approval",
        "scope": "system",
    },
}


# ============ 交易对级别配置 ============

SYMBOL_APPROVAL_CONFIGS: Dict[str, Dict[str, Any]] = {
    # BTC/USDT 配置
    "BTC/USDT": {
        "mode": "hybrid",
        "timeout_seconds": 300,
        "auto_threshold_usd": 1000,
        "delayed_threshold_seconds": 120,
    },
    # ETH/USDT 配置
    "ETH/USDT": {
        "mode": "hybrid",
        "timeout_seconds": 300,
        "auto_threshold_usd": 500,
        "delayed_threshold_seconds": 90,
    },
    # 山寨币默认配置（更严格）
    "_default": {
        "mode": "manual",
        "timeout_seconds": 600,
        "auto_threshold_usd": 100,
        "delayed_threshold_seconds": 60,
    },
}


# ============ 导出 ============

__all__ = [
    "APPROVAL_CONFIGS",
    "APPROVAL_SCHEMAS",
    "SYMBOL_APPROVAL_CONFIGS",
    # 常量
    "TRADING_MODE_DEFAULT",
    "TIMEOUT_SECONDS_DEFAULT",
    "MAX_RETRIES_DEFAULT",
    "RECALCULATE_ON_TIMEOUT_DEFAULT",
    "SIGNAL_EXPIRES_SECONDS_DEFAULT",
    "DELAYED_THRESHOLD_SECONDS_DEFAULT",
    "PRICE_CHANGE_THRESHOLD_DEFAULT",
    "AUTO_THRESHOLD_USD_DEFAULT",
    "NEW_SIGNAL_EXPIRES_SECONDS_DEFAULT",
]
