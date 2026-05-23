"""
Signal Runtime - Kafka 发布者

职责：
- Kafka 连接管理
- 消息发布
- 重试机制
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, Optional

from infrastructure.logging import get_logger


class SignalPublisher:
    """
    Signal Runtime Kafka 发布者
    
    只负责消息发布，不包含业务逻辑。
    """
    
    def __init__(
        self,
        bootstrap_servers: str,
        topic: str,
    ):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        
        self.logger = get_logger("signal_publisher")
        self._producer = None
        self._running = False
    
    async def start(self) -> None:
        """启动发布者"""
        try:
            from infrastructure.messaging import get_broker
            
            self._producer = get_broker(self.bootstrap_servers)
            await self._producer.start()
            
            self._running = True
            self.logger.info(f"Publisher started: {self.topic}")
            
        except Exception as e:
            self.logger.error(f"Failed to start publisher: {e}")
            raise
    
    async def stop(self) -> None:
        """停止发布者"""
        self._running = False
        
        if self._producer:
            await self._producer.stop()
        
        self.logger.info("Publisher stopped")
    
    async def publish(
        self,
        message: Dict[str, Any],
        key: str = None,
        retries: int = 3,
    ) -> bool:
        """发布消息"""
        if not self._running or not self._producer:
            return False
        
        for attempt in range(retries):
            try:
                await self._producer.publish(
                    message=message,
                    topic=self.topic,
                    key=key,
                )
                return True
            except Exception as e:
                self.logger.warning(f"Publish attempt {attempt + 1} failed: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(0.5 * (attempt + 1))
        
        self.logger.error(f"Failed to publish after {retries} attempts")
        return False
    
    async def is_healthy(self) -> bool:
        """检查健康状态"""
        return self._running and self._producer is not None
