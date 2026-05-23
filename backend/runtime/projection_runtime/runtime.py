"""
Projection Runtime - CQRS 投影运行时

职责（仅运行时编排）：
- Kafka 消费
- 生命周期管理
- 重试机制
- 健康检查
- 指标收集
- 写入 RuntimeStateStore（统一状态来源）

业务逻辑：调用 services/projection_service/projections/
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from runtime.base import BaseRuntime, RuntimeConfig
from runtime.shared import (
    RuntimeLifecycle,
    RuntimeMetrics,
    RuntimeConsumer,
    ConsumerConfig,
    RuntimePublisher,
    PublisherConfig,
    RuntimeHealthCheck,
)
from runtime.state import get_runtime_state_store
from infrastructure.messaging import Topics
from infrastructure.messaging.kafka_config import ConsumerGroup
from infrastructure.config.defaults.infrastructure.middleware import KAFKA_BOOTSTRAP_SERVERS
from infrastructure.runtime_clock import get_clock, ClockMode, now_ms
from infrastructure.feature_availability import get_systematic_guard
from infrastructure.label_isolation import get_label_store
from infrastructure.event.event_ordering import EventOrderingDeterminism
from infrastructure.event.unified_schema import UnifiedEvent


class ProjectionConfig(RuntimeConfig):
    name: str = "projection_runtime"
    batch_size: int = 100
    flush_interval: float = 1.0


class ProjectionRuntime(BaseRuntime):

    EVENT_TYPE_TO_CHANNEL = {
        "price_update": "channel:prices",
        "raw_data": "channel:dashboard",
        "news": "channel:dashboard",
        "signal": "channel:signal",
        "event": "channel:timeline",
        "market": "channel:dashboard",
        "order": "channel:order",
        "position": "channel:position",
        "risk": "channel:risk",
        "decision": "channel:decision",
    }

    EVENT_TYPE_TO_STATE_TYPE = {
        "price_update": "market",
        "raw_data": "market",
        "market": "market",
        "news": "market",
        "signal": "signal",
        "decision": "signal",
        "order": "execution",
        "position": "portfolio",
        "risk": "risk",
        "feature": "feature",
    }

    def __init__(self, config: ProjectionConfig = None):
        config = config or ProjectionConfig.from_env()
        super().__init__(config)
        self.config: ProjectionConfig = config

        self._clock = get_clock()
        self._availability_guard = get_systematic_guard()
        self._label_store = get_label_store()
        self._event_ordering = EventOrderingDeterminism()

        self.lifecycle: Optional[RuntimeLifecycle] = None
        self.metrics: Optional[RuntimeMetrics] = None
        self.health_check: Optional[RuntimeHealthCheck] = None

        self.consumer: Optional[RuntimeConsumer] = None
        self.publisher: Optional[RuntimePublisher] = None
        self.projections: List[Any] = []

        self._redis: Any = None
        self._redis_pubsub: Any = None

        self._state_store = get_runtime_state_store()

    async def initialize(self) -> None:
        self.logger.info("Initializing Projection Runtime with time-causal infrastructure...")

        self.lifecycle = RuntimeLifecycle("projection")
        self.metrics = RuntimeMetrics("projection")
        self.health_check = RuntimeHealthCheck("projection")

        try:
            import redis.asyncio as aioredis
            from infrastructure.config.defaults.infrastructure.cache import CACHE_CONFIGS
            redis_url = CACHE_CONFIGS.get("cache.redis_url", "redis://localhost:6379/0")
            self._redis = aioredis.from_url(redis_url, decode_responses=True)
            await self._redis.ping()
            self.logger.info("Redis connected for pub/sub")
        except Exception as e:
            self.logger.warning(f"Redis connection failed: {e}. Continuing without pub/sub.")

        try:
            import asyncio
            kafka_servers = KAFKA_BOOTSTRAP_SERVERS
            self.logger.info(f"Connecting to Kafka at: {kafka_servers}")

            await asyncio.sleep(5)

            self.consumer = RuntimeConsumer(ConsumerConfig(
                bootstrap_servers=kafka_servers,
                topics=[Topics.EVENTS, Topics.FACTORS],
                group_id=ConsumerGroup.PROJECTION_RUNTIME,
                auto_offset_reset="earliest",
            ))
            await self.consumer.start()
            self.logger.info("Kafka consumer initialized successfully")
        except Exception as e:
            self.logger.error(f"Kafka consumer init failed: {e}")
            self.logger.warning("Continuing without Kafka consumer")

        try:
            from services.projection_service.projections import (
                DashboardProjection,
                DecisionProjection,
                RiskProjection,
                PositionProjection,
                EventTimelineProjection,
            )

            self.projections = [
                DashboardProjection(),
                DecisionProjection(),
                RiskProjection(),
                PositionProjection(),
                EventTimelineProjection(),
            ]

            for projection in self.projections:
                try:
                    await projection.initialize()
                    self.logger.info(f"Initialized: {projection.name}")
                except Exception as e:
                    self.logger.error(f"Failed to initialize {projection.name}: {e}")

        except Exception as e:
            self.logger.warning(f"Projections init failed: {e}")

        self.health_check.register_check("projections", self._check_projections)
        self.health_check.register_check("consumer", self._check_consumer)

        self.logger.info("Projection Runtime initialized successfully")

    async def _check_projections(self) -> bool:
        return len(self.projections) > 0

    async def _check_consumer(self) -> bool:
        return self.consumer is not None and await self.consumer.is_healthy()

    async def shutdown(self) -> None:
        self.logger.info("Shutting down Projection Runtime...")

        for projection in self.projections:
            try:
                await projection.shutdown()
            except Exception as e:
                self.logger.error(f"Error shutting down {projection.name}: {e}")

        if self.consumer:
            await self.consumer.stop()

        if self._redis:
            await self._redis.close()

        self.logger.info(f"Projection Runtime stopped. Stats: {self.metrics.to_dict()}")

    async def run(self) -> None:
        self.logger.info("Starting Projection Runtime main loop...")

        await self.lifecycle.transition_to_running()

        while not self.context.is_shutdown_requested():
            try:
                message = await self._consume_event(timeout=1.0)
                if message:
                    await self._dispatch_event(message)

            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                self.metrics.increment("errors")
                await self.lifecycle.handle_error(e)

    async def _consume_event(self, timeout: float = 1.0) -> Optional[Dict[str, Any]]:
        if self.consumer:
            return await self.consumer.consume(timeout)
        return None

    async def _dispatch_event(self, message: Dict[str, Any]) -> None:
        self.metrics.increment("events_received")

        event = message.get("value", message)
        event_type = event.get("event_type", "unknown")

        try:
            unified_event = UnifiedEvent.from_dict(event)
            if self._event_ordering:
                if not self._event_ordering.validate_event_order(unified_event):
                    self.logger.warning(f"Event out of order: {unified_event.event_id}")
        except Exception as e:
            self.logger.debug(f"Event schema validation skipped: {e}")

        if self._label_store:
            self._label_store.ensure_isolation("projection")

        with self.metrics.timing("event_processing"):
            for projection in self.projections:
                try:
                    await projection.process_event(event)
                except Exception as e:
                    self.logger.error(f"Error in {projection.name}: {e}")

        self._update_state_store(event_type, event)

        self.metrics.increment("events_processed")

    def _update_state_store(self, event_type: str, event: Dict[str, Any]) -> None:
        try:
            state_type = self.EVENT_TYPE_TO_STATE_TYPE.get(event_type)
            if state_type:
                self._state_store.update(state_type, {
                    "last_event": event,
                    "last_update": datetime.fromtimestamp(now_ms() / 1000).isoformat(),
                    "last_event_type": event_type,
                })
        except Exception as e:
            self.logger.error(f"Error updating state store: {e}")

    def get_projected_state(self, state_type: str) -> Dict[str, Any]:
        return self._state_store.get_state(state_type)

    async def health_check(self) -> Dict[str, Any]:
        health = await super().health_check()
        health.update({
            "lifecycle": self.lifecycle.to_dict() if self.lifecycle else {},
            "metrics": self.metrics.to_dict() if self.metrics else {},
            "projections_count": len(self.projections),
        })
        return health


_projection_runtime: Optional[ProjectionRuntime] = None


def get_projection_runtime() -> ProjectionRuntime:
    global _projection_runtime
    if _projection_runtime is None:
        _projection_runtime = ProjectionRuntime()
    return _projection_runtime


async def main():
    print("=" * 60)
    print("Projection Runtime - CQRS Projection")
    print("=" * 60)

    runtime = get_projection_runtime()
    await runtime.start()


if __name__ == "__main__":
    asyncio.run(main())
