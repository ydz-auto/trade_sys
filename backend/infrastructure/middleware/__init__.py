"""
TradeAgent Middleware Module
消息中间件（Kafka）封装
"""

from infrastructure.middleware.kafka import (
    FastStreamKafka,
    KafkaPublisher,
    KafkaConsumer,
    get_kafka_broker,
    get_kafka_publisher,
    get_kafka_consumer,
    init_kafka,
    close_kafka,
)
from infrastructure.middleware.config import (
    KafkaConfig,
    MiddlewareConfig,
    get_middleware_config,
    update_middleware_config,
    KAFKA_TOPICS,
    MIDDLEWARE_SERVICE_DEPENDENCIES,
)

__all__ = [
    "FastStreamKafka",
    "KafkaPublisher",
    "KafkaConsumer",
    "get_kafka_broker",
    "get_kafka_publisher",
    "get_kafka_consumer",
    "init_kafka",
    "close_kafka",
    "KafkaConfig",
    "MiddlewareConfig",
    "get_middleware_config",
    "update_middleware_config",
    "KAFKA_TOPICS",
    "MIDDLEWARE_SERVICE_DEPENDENCIES",
]
