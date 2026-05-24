"""
Kafka 统一配置

所有 Kafka 相关配置的单一来源
"""

from dataclasses import dataclass, field
from typing import Optional
import os

from infrastructure.config.defaults.infrastructure.middleware import (
    MIDDLEWARE_CONFIGS,
    KAFKA_TOPICS,
    MIDDLEWARE_SERVICE_DEPENDENCIES,
)


class ConsumerGroup:
    """Consumer Group ID 命名规范

    格式: tradeagent-{runtime_name}
    例如: tradeagent-signal, tradeagent-execution
    """
    NAMESPACE = "tradeagent"

    @classmethod
    def for_runtime(cls, runtime_name: str) -> str:
        return f"{cls.NAMESPACE}-{runtime_name}"

    SIGNAL_RUNTIME = "tradeagent-signal"
    EXECUTION_RUNTIME = "tradeagent-execution"
    PROJECTION_RUNTIME = "tradeagent-projection"
    INGESTION_RUNTIME = "tradeagent-ingestion"
    NARRATIVE_RUNTIME = "tradeagent-narrative"
    MONITORING_RUNTIME = "tradeagent-monitoring"
    CORRELATION_RUNTIME = "tradeagent-correlation"
    SCHEDULER_RUNTIME = "tradeagent-scheduler"
    DATA_WORKER = "tradeagent-data-worker"
    STRATEGY_WORKER = "tradeagent-strategy-worker"
    EXECUTION_WORKER = "tradeagent-execution-worker"


@dataclass
class KafkaConsumerConfig:
    """Kafka Consumer 统一配置

    优化配置以增强容错能力和处理 leader 切换
    """
    session_timeout_ms: int = 45000
    heartbeat_interval_ms: int = 15000
    max_poll_records: int = 500
    max_poll_interval_ms: int = 300000
    enable_auto_commit: bool = True
    auto_commit_interval_ms: int = 5000
    auto_offset_reset: str = "latest"
    request_timeout_ms: int = 60000
    retry_attempts: int = 15
    retry_delay_ms: int = 3000
    metadata_max_age_ms: int = 300000
    connections_max_idle_ms: int = 540000
    api_version_request_timeout_ms: int = 20000


@dataclass
class KafkaProducerConfig:
    """Kafka Producer 统一配置"""
    acks: str = "all"
    retries: int = 3
    batch_size: int = 16384
    linger_ms: int = 5
    compression_type: str = "gzip"
    max_in_flight_requests_per_connection: int = 5
    request_timeout_ms: int = 30000
    delivery_timeout_ms: int = 120000


@dataclass
class KafkaConfig:
    """Kafka 统一配置"""
    bootstrap_servers: str = field(default_factory=lambda: _resolve_kafka_servers())
    client_id: str = "tradeagent"

    consumer: KafkaConsumerConfig = field(default_factory=KafkaConsumerConfig)
    producer: KafkaProducerConfig = field(default_factory=KafkaProducerConfig)

    @classmethod
    def from_env(cls) -> "KafkaConfig":
        return cls(
            bootstrap_servers=_resolve_kafka_servers(),
            client_id=os.environ.get("KAFKA_CLIENT_ID", "tradeagent"),
        )


def _resolve_kafka_servers() -> str:
    env_val = os.environ.get("KAFKA_BOOTSTRAP_SERVERS")
    if env_val:
        return env_val
    try:
        from infrastructure.config.startup.settings import get_startup_settings
        return get_startup_settings().kafka.bootstrap_servers
    except Exception:
        return "localhost:9092"


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


DEFAULT_KAFKA_CONFIG = KafkaConfig()
DEFAULT_CONSUMER_CONFIG = KafkaConsumerConfig()
DEFAULT_PRODUCER_CONFIG = KafkaProducerConfig()
