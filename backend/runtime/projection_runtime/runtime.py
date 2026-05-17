"""
Projection Runtime - CQRS 投影运行时

职责（仅运行时编排）：
- Kafka 消费
- 生命周期管理
- 重试机制
- 健康检查
- 指标收集

业务逻辑：调用 services/projection_service/projections/
"""

import asyncio
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
from infrastructure.messaging import Topics
from infrastructure.messaging.kafka_config import ConsumerGroup
from shared.config.defaults.infrastructure.middleware import KAFKA_BOOTSTRAP_SERVERS


class ProjectionConfig(RuntimeConfig):
    """Projection Runtime 配置"""
    name: str = "projection_runtime"
    batch_size: int = 100
    flush_interval: float = 1.0


class ProjectionRuntime(BaseRuntime):
    """
    Projection Runtime - CQRS 投影运行时
    
    只负责运行时编排，业务逻辑在 services/projection_service/projections/
    """
    
    def __init__(self, config: ProjectionConfig = None):
        config = config or ProjectionConfig.from_env()
        super().__init__(config)
        self.config: ProjectionConfig = config
        
        self.lifecycle: Optional[RuntimeLifecycle] = None
        self.metrics: Optional[RuntimeMetrics] = None
        self.health_check: Optional[RuntimeHealthCheck] = None
        
        self.consumer: Optional[RuntimeConsumer] = None
        self.projections: List[Any] = []
    
    async def initialize(self) -> None:
        """初始化运行时组件"""
        self.logger.info("Initializing Projection Runtime...")
        
        self.lifecycle = RuntimeLifecycle("projection")
        self.metrics = RuntimeMetrics("projection")
        self.health_check = RuntimeHealthCheck("projection")
        
        try:
            import asyncio
            kafka_servers = KAFKA_BOOTSTRAP_SERVERS
            self.logger.info(f"Connecting to Kafka at: {kafka_servers}")
            
            await asyncio.sleep(5)
            
            self.consumer = RuntimeConsumer(ConsumerConfig(
                bootstrap_servers=kafka_servers,
                topics=[Topics.EVENTS],
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
        """检查投影器"""
        return len(self.projections) > 0
    
    async def _check_consumer(self) -> bool:
        """检查Kafka消费者"""
        return self.consumer is not None and await self.consumer.is_healthy()
    
    async def shutdown(self) -> None:
        """关闭运行时组件"""
        self.logger.info("Shutting down Projection Runtime...")
        
        for projection in self.projections:
            try:
                await projection.shutdown()
            except Exception as e:
                self.logger.error(f"Error shutting down {projection.name}: {e}")
        
        if self.consumer:
            await self.consumer.stop()
        
        self.logger.info(f"Projection Runtime stopped. Stats: {self.metrics.to_dict()}")
    
    async def run(self) -> None:
        """主运行循环"""
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
        """消费事件消息"""
        if self.consumer:
            return await self.consumer.consume(timeout)
        return None
    
    async def _dispatch_event(self, message: Dict[str, Any]) -> None:
        """分发事件到投影器（运行时编排）"""
        self.metrics.increment("events_received")
        
        event = message.get("value", message)
        event_type = event.get("event_type", "unknown")
        
        with self.metrics.timing("event_processing"):
            for projection in self.projections:
                try:
                    await projection.process_event(event)
                except Exception as e:
                    self.logger.error(f"Error in {projection.name}: {e}")
        
        self.metrics.increment("events_processed")
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        health = await super().health_check()
        health.update({
            "lifecycle": self.lifecycle.to_dict() if self.lifecycle else {},
            "metrics": self.metrics.to_dict() if self.metrics else {},
            "projections_count": len(self.projections),
        })
        return health


_projection_runtime: Optional[ProjectionRuntime] = None


def get_projection_runtime() -> ProjectionRuntime:
    """获取 Projection Runtime 单例"""
    global _projection_runtime
    if _projection_runtime is None:
        _projection_runtime = ProjectionRuntime()
    return _projection_runtime


async def main():
    """主入口"""
    print("=" * 60)
    print("Projection Runtime - CQRS Projection")
    print("=" * 60)
    
    runtime = get_projection_runtime()
    await runtime.start()


if __name__ == "__main__":
    asyncio.run(main())
