from typing import Optional, Dict, Any, Callable, Type, Union, TYPE_CHECKING
from pydantic import BaseModel

from infrastructure.config.defaults.infrastructure.middleware import KAFKA_BOOTSTRAP_SERVERS

try:
    from faststream import FastStream
    from faststream.kafka import KafkaBroker
    FASTSTREAM_AVAILABLE = True
except ImportError:
    FASTSTREAM_AVAILABLE = False
    FastStream = None
    KafkaBroker = None

if TYPE_CHECKING:
    from faststream import FastStream as FastStreamType
    from faststream.kafka import KafkaBroker as KafkaBrokerType

_broker: Optional[Any] = None


class KafkaBrokerWrapper:
    def __init__(self, bootstrap_servers: str = None):
        if not FASTSTREAM_AVAILABLE:
            raise RuntimeError("FastStream not installed. Run: pip install faststream[kafka]")

        self.bootstrap_servers = bootstrap_servers or KAFKA_BOOTSTRAP_SERVERS
        self._broker: Optional[Any] = None
        self._app: Optional[Any] = None
        self._publishers: Dict[str, Any] = {}
        self._subscribers: Dict[str, Callable] = {}
        self._started = False

    def get_broker(self):
        if self._broker is None:
            self._broker = KafkaBroker(self.bootstrap_servers)
        return self._broker

    async def start(self) -> None:
        if not self._started:
            broker = self.get_broker()
            await broker.start()
            self._started = True

    async def stop(self) -> None:
        if self._started:
            broker = self.get_broker()
            await broker.close()
            self._started = False

    async def __aenter__(self) -> "KafkaBrokerWrapper":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.stop()

    def publisher(
        self,
        topic: str,
        schema: Optional[Type[BaseModel]] = None,
        description: str = "",
    ) -> Callable:
        broker = self.get_broker()
        pub = broker.publisher(topic, description=description, schema=schema)
        self._publishers[topic] = pub
        return pub

    def subscriber(
        self,
        topic: str,
        schema: Optional[Type[BaseModel]] = None,
        description: str = "",
    ) -> Callable:
        broker = self.get_broker()

        def decorator(func: Callable) -> Callable:
            self._subscribers[topic] = func
            if schema:
                broker.subscriber(topic, schema=schema, description=description)(func)
            else:
                broker.subscriber(topic, description=description)(func)
            return func
        return decorator

    async def publish(
        self,
        message: Union[BaseModel, Dict[str, Any]],
        topic: str,
        key: Optional[str] = None,
    ) -> None:
        broker = self.get_broker()
        if topic not in self._publishers:
            self.publisher(topic)
        await broker.publish(message=message, topic=topic, key=key)

    def create_app(self, title: str = "TradeAgent", version: str = "1.0.0"):
        if self._app is None:
            self._app = FastStream(self.get_broker())
        return self._app

    async def run(self) -> None:
        if self._app is None:
            self._app = self.create_app()
        await self._app.run()

    async def close(self) -> None:
        await self.stop()


import os

_broker_instance: Optional["KafkaBrokerWrapper"] = None


def get_broker(bootstrap_servers: str = None) -> "KafkaBrokerWrapper":
    global _broker_instance
    if _broker_instance is None:
        servers = bootstrap_servers or KAFKA_BOOTSTRAP_SERVERS
        _broker_instance = KafkaBrokerWrapper(servers)
    return _broker_instance


def reset_broker() -> None:
    global _broker_instance, _broker
    _broker_instance = None
    _broker = None
