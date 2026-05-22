import json
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from infrastructure.messaging.topics import Topics

logger = logging.getLogger(__name__)

try:
    from aiokafka import AIOKafkaProducer
    AIOKAFKA_AVAILABLE = True
except ImportError:
    AIOKAFKA_AVAILABLE = False


class DownloadEventEmitter:
    def __init__(self):
        self._producer: Optional[AIOKafkaProducer] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._available = False
        self._init()

    def _init(self):
        if not AIOKAFKA_AVAILABLE:
            logger.warning("aiokafka not available, events will be logged only")
            return
        try:
            from shared.config.defaults.infrastructure.middleware import KAFKA_BOOTSTRAP_SERVERS
            self._loop = asyncio.new_event_loop()
            self._producer = self._loop.run_until_complete(
                self._start_producer(KAFKA_BOOTSTRAP_SERVERS)
            )
            self._available = True
        except Exception as e:
            logger.warning(f"Kafka not available, events will be logged only: {e}")

    async def _start_producer(self, bootstrap_servers: str):
        producer = AIOKafkaProducer(bootstrap_servers=bootstrap_servers)
        await producer.start()
        return producer

    def emit(self, source: str, symbol: str, data_path: str, timeframe: str = None):
        event = {
            "event_type": "data_downloaded",
            "source": source,
            "symbol": symbol,
            "timeframe": timeframe,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data_path": str(data_path),
        }
        if self._available:
            try:
                self._loop.run_until_complete(self._publish(event))
                return
            except Exception as e:
                logger.warning(f"Failed to publish event to Kafka, logging instead: {e}")
        logger.info(f"data_downloaded: {json.dumps(event)}")

    async def _publish(self, event: dict):
        await self._producer.send_and_wait(
            Topics.RAW_DATA,
            json.dumps(event).encode("utf-8"),
            key=event.get("symbol", "").encode("utf-8"),
        )

    def close(self):
        if self._available and self._producer and self._loop:
            try:
                self._loop.run_until_complete(self._producer.stop())
            except Exception:
                pass
            self._loop.close()
            self._available = False
