"""
Middleware 配置 - 基础设施配置

Topic 定义:
- 常量定义: infrastructure/messaging/topics.py (Topics 类)
- 字典映射: 本文件 (KAFKA_TOPICS)
- 两者保持同步
"""

import os

KAFKA_TOPICS = {
    "raw_data": "tradeagent.raw_data",
    "features": "tradeagent.features",
    "factors": "tradeagent.factors",
    "regimes": "tradeagent.regimes",
    "risk_alerts": "tradeagent.risk_alerts",
    "trading_signals": "tradeagent.trading_signals",
    "order_events": "tradeagent.order_events",
    "execution_results": "tradeagent.execution_results",
    "feedback_data": "tradeagent.feedback_data",
    "signals": "tradeagent.signals",
    "decisions": "tradeagent.decisions.all",
    "orders": "tradeagent.orders",
    "events": "tradeagent.events",
    "alerts": "tradeagent.alerts",
}


def _resolve_kafka_default() -> str:
    try:
        from infrastructure.config.startup.settings import get_startup_settings
        return get_startup_settings().kafka.bootstrap_servers
    except Exception:
        return "localhost:9092"


KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS") or _resolve_kafka_default()
KAFKA_CLIENT_ID = os.environ.get("KAFKA_CLIENT_ID", "tradeagent")


MIDDLEWARE_CONFIGS = {
    "middleware.kafka.bootstrap_servers": KAFKA_BOOTSTRAP_SERVERS,
    "middleware.kafka.client_id": KAFKA_CLIENT_ID,
    "middleware.kafka.consumer_group": "tradeagent",
    "middleware.kafka.auto_offset_reset": "latest",
    "middleware.kafka.enable_auto_commit": True,
    "middleware.kafka.max_poll_records": 500,
    "middleware.kafka.session_timeout_ms": 45000,
    "middleware.kafka.heartbeat_interval_ms": 15000,
}


MIDDLEWARE_SCHEMAS = {
    "middleware.kafka.bootstrap_servers": {
        "value_type": "string",
        "default": "localhost:9092",
        "description": "Kafka bootstrap servers (comma-separated)",
    },
    "middleware.kafka.client_id": {
        "value_type": "string",
        "default": "tradeagent",
        "description": "Kafka client ID",
    },
    "middleware.kafka.consumer_group": {
        "value_type": "string",
        "default": "tradeagent",
        "description": "Kafka consumer group ID",
    },
    "middleware.kafka.auto_offset_reset": {
        "value_type": "string",
        "default": "latest",
        "description": "Kafka auto offset reset policy",
        "options": ["earliest", "latest"],
    },
    "middleware.kafka.enable_auto_commit": {
        "value_type": "bool",
        "default": True,
        "description": "Enable Kafka auto commit",
    },
    "middleware.kafka.max_poll_records": {
        "value_type": "int",
        "default": 500,
        "description": "Max records per poll",
        "min_value": 1,
        "max_value": 100000,
    },
    "middleware.kafka.session_timeout_ms": {
        "value_type": "int",
        "default": 45000,
        "description": "Kafka session timeout in milliseconds",
    },
    "middleware.kafka.heartbeat_interval_ms": {
        "value_type": "int",
        "default": 15000,
        "description": "Kafka heartbeat interval in milliseconds",
    },
}


MIDDLEWARE_SERVICE_DEPENDENCIES = {
    "data_service": ["kafka", "redis", "clickhouse"],
    "feature_service": ["kafka", "redis", "clickhouse"],
    "factor_service": ["kafka", "redis", "clickhouse"],
    "risk_service": ["kafka", "redis", "postgresql"],
    "decision_service": ["kafka", "redis", "postgresql"],
    "position_service": ["redis", "postgresql"],
    "execution_service": ["kafka", "redis", "postgresql"],
    "auth_service": ["redis", "postgresql"],
    "llm_service": ["redis"],
    "feedback_service": ["kafka", "redis", "postgresql", "clickhouse"],
    "state_service": ["kafka", "redis", "postgresql"],
    "config_service": ["redis", "postgresql"],
    "monitor_service": ["redis"],
    "notification_service": ["kafka", "redis"],
    "regime_service": ["kafka", "redis", "clickhouse"],
    "portfolio_service": ["redis", "postgresql"],
    "control_service": ["kafka", "redis", "postgresql"],
    "api-gateway": ["redis"],
}
