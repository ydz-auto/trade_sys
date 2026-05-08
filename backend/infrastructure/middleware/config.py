"""
Middleware 配置
从 shared.config 导入基础配置，业务配置保留在此
"""

from typing import Optional
from dataclasses import dataclass, field

from shared.config.defaults.infrastructure import (
    MIDDLEWARE_CONFIGS,
    KAFKA_TOPICS,
    MIDDLEWARE_SERVICE_DEPENDENCIES,
)


@dataclass
class KafkaConfig:
    bootstrap_servers: str = MIDDLEWARE_CONFIGS.get("middleware.kafka.bootstrap_servers", "localhost:9092")
    client_id: str = MIDDLEWARE_CONFIGS.get("middleware.kafka.client_id", "tradeagent")
    consumer_group: str = MIDDLEWARE_CONFIGS.get("middleware.kafka.consumer_group", "tradeagent")
    auto_offset_reset: str = MIDDLEWARE_CONFIGS.get("middleware.kafka.auto_offset_reset", "latest")
    enable_auto_commit: bool = MIDDLEWARE_CONFIGS.get("middleware.kafka.enable_auto_commit", True)
    max_poll_records: int = MIDDLEWARE_CONFIGS.get("middleware.kafka.max_poll_records", 100)
    session_timeout_ms: int = MIDDLEWARE_CONFIGS.get("middleware.kafka.session_timeout_ms", 30000)
    heartbeat_interval_ms: int = MIDDLEWARE_CONFIGS.get("middleware.kafka.heartbeat_interval_ms", 10000)


@dataclass
class MiddlewareConfig:
    kafka: KafkaConfig = field(default_factory=KafkaConfig)


_middleware_config: Optional[MiddlewareConfig] = None


def get_middleware_config() -> MiddlewareConfig:
    global _middleware_config
    if _middleware_config is None:
        _middleware_config = MiddlewareConfig()
    return _middleware_config


def update_middleware_config(
    kafka: Optional[KafkaConfig] = None,
) -> MiddlewareConfig:
    global _middleware_config

    if _middleware_config is None:
        _middleware_config = MiddlewareConfig()

    if kafka:
        _middleware_config.kafka = kafka

    return _middleware_config


__all__ = [
    "KafkaConfig",
    "MiddlewareConfig",
    "KAFKA_TOPICS",
    "MIDDLEWARE_SERVICE_DEPENDENCIES",
    "get_middleware_config",
    "update_middleware_config",
]