"""
Signal Runtime - Kafka 消费者

职责：
- Kafka 连接管理
- 消息消费
- 重试机制
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from infrastructure.logging import get_logger


class SignalConsumer:
    """
    Signal Runtime Kafka 消费者
    
    只负责消息消费，不包含业务逻辑。
    """
    
    def __init__(
        self,
        bootstrap_servers: str,
        topics: List[str],
        group_id: str = "signal-runtime",
    ):
        self.bootstrap_servers = bootstrap_servers
        self.topics = topics
        self.group_id = group_id
        
        self.logger = get_logger("signal_consumer")
        self._consumer = None
        self._running = False
    
    async def start(self) -> None:
        """启动消费者"""
        try:
            from infrastructure.messaging.broker import get_broker
            
            self._consumer = get_broker(self.bootstrap_servers)
            await self._consumer.start()
            
            self._running = True
            self.logger.info(f"Consumer started: {self.topics}")
            
        except Exception as e:
            self.logger.error(f"Failed to start consumer: {e}")
            raise
    
    async def stop(self) -> None:
        """停止消费者"""
        self._running = False
        
        if self._consumer:
            await self._consumer.stop()
        
        self.logger.info("Consumer stopped")
    
    async def consume(self, timeout: float = 1.0) -> Optional[Dict[str, Any]]:
        """消费消息"""
        if not self._running or not self._consumer:
            return None
        
        try:
            message = await self._consumer.consume(timeout=timeout)
            return message
        except Exception as e:
            self.logger.error(f"Consume error: {e}")
            return None
    
    async def is_healthy(self) -> bool:
        """检查健康状态"""
        return self._running and self._consumer is not None
