"""
Base Projection - 所有 Projection 的基类

提供：
1. Redis 连接管理
2. WebSocket 推送
3. Schema 验证
4. 统计和监控
"""

import json
import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field

from infrastructure.logging import get_logger
from infrastructure.cache.redis_client import RedisClient, get_redis_client, init_redis
from infrastructure.websocket.manager import ws_manager
from infrastructure.messaging.schema_registry import get_schema_registry, BaseEventV2


@dataclass
class ProjectionStats:
    """Projection 统计"""
    events_received: int = 0
    events_processed: int = 0
    events_validated: int = 0
    events_rejected: int = 0
    redis_updates: int = 0
    ws_pushes: int = 0
    errors: int = 0
    last_event_time: Optional[datetime] = None


@dataclass
class SchemaValidationResult:
    """Schema 验证结果"""
    is_valid: bool
    event_type: str
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    transformed_event: Optional[Dict[str, Any]] = None


class BaseProjection(ABC):
    """
    Projection 基类
    
    子类需要实现：
    - topics: 订阅的 Kafka topics
    - process_event(event): 处理事件逻辑
    """
    
    def __init__(self, name: str, validate_schema: bool = True):
        self.name = name
        self.logger = get_logger(f"projection.{name}")
        self.redis: Optional[RedisClient] = None
        self._stats = ProjectionStats()
        self._running = False
        self._validate_schema = validate_schema
        self._schema_registry = None
    
    async def initialize(self) -> None:
        """初始化 Projection"""
        self.logger.info(f"Initializing {self.name} projection...")
        
        try:
            self.redis = await init_redis()
            self.logger.info(f"{self.name}: Redis connected")
        except Exception as e:
            self.logger.warning(f"{self.name}: Redis connection failed: {e}")
            self.redis = None
        
        if self._validate_schema:
            try:
                self._schema_registry = get_schema_registry()
                self.logger.info(f"{self.name}: Schema registry loaded")
            except Exception as e:
                self.logger.warning(f"{self.name}: Schema registry failed: {e}")
        
        self._running = True
        self.logger.info(f"{self.name} projection initialized")
    
    async def shutdown(self) -> None:
        """关闭 Projection"""
        self.logger.info(f"Shutting down {self.name} projection...")
        self._running = False
        self.logger.info(f"{self.name} stopped. Stats: {self._stats.__dict__}")
    
    @property
    @abstractmethod
    def topics(self) -> List[str]:
        """订阅的 Kafka topics"""
        pass
    
    @abstractmethod
    async def process_event(self, event: Dict[str, Any]) -> None:
        """
        处理事件
        
        子类实现具体逻辑：
        1. 解析事件
        2. 更新 Redis
        3. 可选推送 WebSocket
        """
        pass
    
    async def validate_event(self, event: Dict[str, Any]) -> SchemaValidationResult:
        """
        验证事件 Schema
        
        Args:
            event: 事件数据
            
        Returns:
            SchemaValidationResult: 验证结果
        """
        self._stats.events_received += 1
        
        if not self._schema_registry:
            return SchemaValidationResult(
                is_valid=True,
                event_type=event.get("event_type", "unknown"),
                transformed_event=event,
            )
        
        event_type = event.get("event_type", "unknown")
        
        try:
            is_valid, error = self._schema_registry.validate_event(event)
            
            if is_valid:
                transformed = self._schema_registry.transform_to_canonical(event)
                self._stats.events_validated += 1
                
                return SchemaValidationResult(
                    is_valid=True,
                    event_type=event_type,
                    transformed_event=transformed,
                )
            else:
                self._stats.events_rejected += 1
                self.logger.warning(f"Schema validation failed: {event_type} - {error}")
                
                return SchemaValidationResult(
                    is_valid=False,
                    event_type=event_type,
                    errors=[error],
                    transformed_event=event,
                )
                
        except Exception as e:
            self._stats.events_rejected += 1
            self.logger.error(f"Schema validation error: {e}")
            
            return SchemaValidationResult(
                is_valid=False,
                event_type=event_type,
                errors=[str(e)],
                transformed_event=event,
            )
    
    async def handle_event(self, event: Dict[str, Any]) -> bool:
        """
        处理事件的入口
        
        自动验证 Schema，然后分发给 process_event
        
        Args:
            event: 事件数据
            
        Returns:
            bool: 是否处理成功
        """
        validation_result = await self.validate_event(event)
        
        if not validation_result.is_valid:
            self.logger.warning(
                f"Event rejected by schema validation: "
                f"{validation_result.event_type} - {validation_result.errors}"
            )
            return False
        
        try:
            await self.process_event(validation_result.transformed_event)
            self._stats.events_processed += 1
            return True
        except Exception as e:
            self.logger.error(f"Event processing error: {e}")
            self._stats.errors += 1
            return False
    
    async def update_redis(self, key: str, value: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """更新 Redis 状态"""
        if not self.redis:
            return False
        
        try:
            await self.redis.set_json(key, value, ex=ttl)
            self._stats.redis_updates += 1
            return True
        except Exception as e:
            self.logger.error(f"Redis update failed: {e}")
            self._stats.errors += 1
            return False
    
    async def get_redis(self, key: str) -> Optional[Dict[str, Any]]:
        """获取 Redis 状态"""
        if not self.redis:
            return None
        
        try:
            return await self.redis.get_json(key)
        except Exception as e:
            self.logger.error(f"Redis get failed: {e}")
            return None
    
    async def append_redis_list(self, key: str, value: Dict[str, Any], max_len: int = 100) -> bool:
        """追加到 Redis List（保持最新 N 条）"""
        if not self.redis:
            return False
        
        try:
            await self.redis.lpush(key, json.dumps(value))
            await self.redis.client.ltrim(key, 0, max_len - 1)
            self._stats.redis_updates += 1
            return True
        except Exception as e:
            self.logger.error(f"Redis list append failed: {e}")
            self._stats.errors += 1
            return False
    
    async def push_websocket(self, channel: str, data: Dict[str, Any]) -> None:
        """推送 WebSocket 消息"""
        try:
            message = {
                "channel": channel,
                "data": data,
                "timestamp": datetime.utcnow().isoformat(),
            }
            await ws_manager.broadcast(message)
            self._stats.ws_pushes += 1
        except Exception as e:
            self.logger.error(f"WebSocket push failed: {e}")
    
    async def publish_redis(self, channel: str, message: Dict[str, Any]) -> None:
        """发布 Redis Pub/Sub 消息"""
        if not self.redis:
            return
        
        try:
            await self.redis.publish(channel, json.dumps(message))
        except Exception as e:
            self.logger.error(f"Redis publish failed: {e}")
    
    def record_event(self) -> None:
        """记录事件处理"""
        self._stats.events_processed += 1
        self._stats.last_event_time = datetime.utcnow()
    
    def get_validation_rate(self) -> float:
        """获取验证通过率"""
        total = self._stats.events_validated + self._stats.events_rejected
        if total == 0:
            return 1.0
        return self._stats.events_validated / total
    
    @property
    def stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "name": self.name,
            "running": self._running,
            "validation_rate": self.get_validation_rate(),
            **self._stats.__dict__,
        }
