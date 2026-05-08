"""
Middleware 配置 - 基础设施配置
"""

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
}


MIDDLEWARE_CONFIGS = {
    "middleware.kafka.bootstrap_servers": "localhost:9092",
    "middleware.kafka.client_id": "tradeagent",
    "middleware.kafka.consumer_group": "tradeagent",
    "middleware.kafka.auto_offset_reset": "latest",
    "middleware.kafka.enable_auto_commit": True,
    "middleware.kafka.max_poll_records": 100,
    "middleware.kafka.session_timeout_ms": 30000,
    "middleware.kafka.heartbeat_interval_ms": 10000,
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
