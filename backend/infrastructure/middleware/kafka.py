"""
Kafka 消息队列 - FastStream 实现
支持 Pydantic Schema 校验，自动 OpenAPI 文档
"""

from typing import Optional, Dict, Any, Callable, Type
from pydantic import BaseModel

from infrastructure.logging import get_logger
logger = get_logger("middleware.kafka")

try:
    from faststream import FastStream
    from faststream.kafka import KafkaBroker
    FASTSTREAM_AVAILABLE = True
except ImportError:
    FASTSTREAM_AVAILABLE = False


class FastStreamKafka:
    def __init__(self, bootstrap_servers: str, client_id: str = "tradeagent"):
        if not FASTSTREAM_AVAILABLE:
            raise RuntimeError("FastStream not installed. Run: pip install faststream[kafka]")

        self.bootstrap_servers = bootstrap_servers
        self.client_id = client_id
        self._broker: Optional[KafkaBroker] = None
        self._app: Optional[FastStream] = None
        self._handlers: Dict[str, Callable] = {}
        self._running = False

    def create_broker(self) -> KafkaBroker:
        self._broker = KafkaBroker(self.bootstrap_servers)
        return self._broker

    def create_app(self, title: str = "TradeAgent Kafka", version: str = "1.0.0") -> FastStream:
        if self._broker is None:
            self.create_broker()
        self._app = FastStream(self._broker, title=title, version=version)
        return self._app

    async def start(self):
        if self._app:
            self._running = True
            await self._app.run()

    async def stop(self):
        self._running = False
        if self._app:
            await self._app.stop()


class KafkaPublisher:
    def __init__(self, broker: KafkaBroker):
        self._broker = broker
        self._publishers: Dict[str, Callable] = {}

    def define_publisher(
        self,
        topic: str,
        schema: Optional[Type[BaseModel]] = None,
    ) -> Callable:
        publisher = self._broker.publisher(topic, schema=schema)
        self._publishers[topic] = publisher
        return publisher

    async def publish(
        self,
        topic: str,
        message: BaseModel | Dict[str, Any],
        key: Optional[str] = None,
    ) -> None:
        if topic not in self._publishers:
            self._broker.publisher(topic)
        await self._broker.publish(message=message, topic=topic, key=key)


class KafkaConsumer:
    def __init__(self, broker: KafkaBroker):
        self._broker = broker
        self._handlers: Dict[str, Callable] = {}

    def subscriber(
        self,
        topic: str,
        schema: Optional[Type[BaseModel]] = None,
    ) -> Callable:
        def decorator(func: Callable) -> Callable:
            self._handlers[topic] = func
            if schema:
                self._broker.subscriber(topic, schema=schema)(func)
            else:
                self._broker.subscriber(topic)(func)
            return func
        return decorator

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass


_broker: Optional[KafkaBroker] = None
_publisher: Optional[KafkaPublisher] = None
_consumer: Optional[KafkaConsumer] = None
_faststream: Optional[FastStreamKafka] = None


def get_kafka_broker(bootstrap_servers: str = "localhost:9092") -> KafkaBroker:
    global _broker
    if _broker is None:
        _broker = KafkaBroker(bootstrap_servers)
    return _broker


def get_kafka_publisher(broker: Optional[KafkaBroker] = None) -> KafkaPublisher:
    global _publisher
    if _publisher is None:
        b = broker or get_kafka_broker()
        _publisher = KafkaPublisher(b)
    return _publisher


def get_kafka_consumer(broker: Optional[KafkaBroker] = None) -> KafkaConsumer:
    global _consumer
    if _consumer is None:
        b = broker or get_kafka_broker()
        _consumer = KafkaConsumer(b)
    return _consumer


async def init_kafka(bootstrap_servers: str = "localhost:9092") -> FastStreamKafka:
    global _faststream
    broker = get_kafka_broker(bootstrap_servers)
    _faststream = FastStreamKafka(bootstrap_servers, client_id="tradeagent-data-service")
    _faststream.create_broker()
    return _faststream


async def close_kafka() -> None:
    global _faststream, _broker, _publisher, _consumer
    if _faststream:
        await _faststream.stop()
    _faststream = None
    _broker = None
    _publisher = None
    _consumer = None
