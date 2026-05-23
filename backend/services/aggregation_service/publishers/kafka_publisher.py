"""
Kafka Publisher - Kafka 发布器
发布聚合后的K线到 Kafka
"""

import json
from typing import Optional, List

from infrastructure.logging import get_logger
from infrastructure.messaging import get_broker
from infrastructure.config.defaults.infrastructure.middleware import KAFKA_BOOTSTRAP_SERVERS

from services.aggregation_service.models.candle_model import Candle
from services.aggregation_service.models.orderbook_model import OrderBookFeature

logger = get_logger("aggregation_service.publisher")


class KafkaPublisher:
    """Kafka 发布器"""

    def __init__(self):
        self.broker = None
        self._initialized = False

    async def initialize(self):
        """初始化"""
        bootstrap_servers = KAFKA_BOOTSTRAP_SERVERS
        self.broker = get_broker(bootstrap_servers)
        await self.broker.start()
        self._initialized = True

    async def publish_candle(self, candle: Candle) -> bool:
        """发布 K线"""
        if not self._initialized or not self.broker:
            return False

        try:
            topic = f"kline.{candle.exchange}.{candle.timeframe.value}.{candle.symbol}"
            key = f"{candle.exchange}:{candle.symbol}:{candle.open_time}"
            value = candle.to_dict()

            await self.broker.publish(message=value, topic=topic, key=key)
            logger.debug(f"Published candle: {topic} {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish candle: {e}")
            return False

    async def publish_candles(self, candles: List[Candle]) -> int:
        """批量发布 K线"""
        success_count = 0
        for candle in candles:
            if await self.publish_candle(candle):
                success_count += 1
        return success_count

    async def publish_orderbook_feature(self, feature: OrderBookFeature) -> bool:
        """发布订单簿特征"""
        if not self._initialized or not self.broker:
            return False

        try:
            topic = f"orderbook.{feature.exchange}.{feature.symbol}"
            key = f"{feature.exchange}:{feature.symbol}:{feature.timestamp}"
            value = feature.to_dict()

            await self.broker.publish(message=value, topic=topic, key=key)
            logger.debug(f"Published orderbook feature: {topic} {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish orderbook feature: {e}")
            return False

    async def shutdown(self):
        """关闭"""
        if self.broker:
            await self.broker.stop()


_publisher: Optional[KafkaPublisher] = None


async def get_kafka_publisher() -> KafkaPublisher:
    """获取 Kafka 发布器"""
    global _publisher
    if _publisher is None:
        _publisher = KafkaPublisher()
        await _publisher.initialize()
    return _publisher
