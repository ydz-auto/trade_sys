"""
WebSocket Gateway - 实时状态推送

架构：
    Projection Service → Redis Pub/Sub → WS Gateway → Frontend

前端通过 WebSocket 订阅频道：
- channel:dashboard  → Dashboard 更新
- channel:decision   → 决策更新
- channel:risk       → 风控更新
- channel:position   → 持仓更新
- channel:timeline   → 事件时间线
- channel:signal     → 信号更新
- channel:order      → 订单更新
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum

from fastapi import WebSocket, WebSocketDisconnect

from infrastructure.logging import get_logger
from infrastructure.cache.redis_client import RedisClient, init_redis
from services.projection_service.state_keys import ProjectionChannels

logger = get_logger("ws_gateway")


class ConnectionState(str, Enum):
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"


@dataclass
class WSConnection:
    """WebSocket 连接信息"""
    websocket: WebSocket
    connection_id: str
    subscribed_channels: Set[str] = field(default_factory=set)
    connected_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    state: ConnectionState = ConnectionState.CONNECTING
    
    def touch(self):
        self.last_activity = datetime.utcnow()


class WSGateway:
    """
    WebSocket Gateway
    
    管理所有 WebSocket 连接，推送实时状态
    """
    
    def __init__(self):
        self.connections: Dict[str, WSConnection] = {}
        self.channel_subscribers: Dict[str, Set[str]] = {}
        self.redis: Optional[RedisClient] = None
        self._running = False
        self._stats = {
            "total_connections": 0,
            "active_connections": 0,
            "messages_sent": 0,
            "errors": 0,
        }
    
    async def initialize(self) -> None:
        """初始化"""
        logger.info("Initializing WS Gateway...")
        
        try:
            self.redis = await init_redis()
            logger.info("WS Gateway: Redis connected")
        except Exception as e:
            logger.warning(f"WS Gateway: Redis connection failed: {e}")
        
        self._running = True
        logger.info("WS Gateway initialized")
    
    async def shutdown(self) -> None:
        """关闭"""
        logger.info("Shutting down WS Gateway...")
        self._running = False
        
        for conn in list(self.connections.values()):
            try:
                await conn.websocket.close()
            except Exception:
                pass
        
        self.connections.clear()
        self.channel_subscribers.clear()
        
        logger.info(f"WS Gateway stopped. Stats: {self._stats}")
    
    async def connect(self, websocket: WebSocket) -> str:
        """
        接受 WebSocket 连接
        
        Returns:
            connection_id
        """
        await websocket.accept()
        
        connection_id = f"conn_{id(websocket)}"
        
        connection = WSConnection(
            websocket=websocket,
            connection_id=connection_id,
            state=ConnectionState.CONNECTED,
        )
        
        self.connections[connection_id] = connection
        self._stats["total_connections"] += 1
        self._stats["active_connections"] = len(self.connections)
        
        logger.info(f"WebSocket connected: {connection_id}. Active: {self._stats['active_connections']}")
        
        await self._send_welcome(connection)
        
        return connection_id
    
    async def disconnect(self, connection_id: str) -> None:
        """断开连接"""
        connection = self.connections.pop(connection_id, None)
        
        if connection:
            for channel in connection.subscribed_channels:
                if channel in self.channel_subscribers:
                    self.channel_subscribers[channel].discard(connection_id)
            
            self._stats["active_connections"] = len(self.connections)
            logger.info(f"WebSocket disconnected: {connection_id}. Active: {self._stats['active_connections']}")
    
    async def _send_welcome(self, connection: WSConnection) -> None:
        """发送欢迎消息"""
        welcome = {
            "type": "welcome",
            "connection_id": connection.connection_id,
            "channels": ProjectionChannels.all(),
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self._send(connection, welcome)
    
    async def _send(self, connection: WSConnection, message: Dict[str, Any]) -> bool:
        """发送消息"""
        try:
            await connection.websocket.send_json(message)
            connection.touch()
            self._stats["messages_sent"] += 1
            return True
        except Exception as e:
            logger.error(f"Send failed: {e}")
            self._stats["errors"] += 1
            return False
    
    async def subscribe(self, connection_id: str, channels: List[str]) -> None:
        """订阅频道"""
        connection = self.connections.get(connection_id)
        if not connection:
            return
        
        for channel in channels:
            connection.subscribed_channels.add(channel)
            
            if channel not in self.channel_subscribers:
                self.channel_subscribers[channel] = set()
            self.channel_subscribers[channel].add(connection_id)
        
        logger.debug(f"{connection_id} subscribed to: {channels}")
        
        await self._send(connection, {
            "type": "subscribed",
            "channels": list(connection.subscribed_channels),
        })
    
    async def unsubscribe(self, connection_id: str, channels: List[str]) -> None:
        """取消订阅"""
        connection = self.connections.get(connection_id)
        if not connection:
            return
        
        for channel in channels:
            connection.subscribed_channels.discard(channel)
            
            if channel in self.channel_subscribers:
                self.channel_subscribers[channel].discard(connection_id)
        
        await self._send(connection, {
            "type": "unsubscribed",
            "channels": list(connection.subscribed_channels),
        })
    
    async def broadcast(self, channel: str, message: Dict[str, Any]) -> int:
        """
        广播消息到频道
        
        Returns:
            发送成功的连接数
        """
        subscribers = self.channel_subscribers.get(channel, set())
        
        if not subscribers:
            return 0
        
        full_message = {
            "channel": channel,
            "data": message,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        success_count = 0
        disconnected = []
        
        for connection_id in subscribers:
            connection = self.connections.get(connection_id)
            if connection:
                if await self._send(connection, full_message):
                    success_count += 1
        
        return success_count
    
    async def broadcast_all(self, message: Dict[str, Any]) -> int:
        """广播到所有连接"""
        full_message = {
            "type": "broadcast",
            "data": message,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        success_count = 0
        for connection in list(self.connections.values()):
            if await self._send(connection, full_message):
                success_count += 1
        
        return success_count
    
    async def handle_message(self, connection_id: str, message: Dict[str, Any]) -> None:
        """处理客户端消息"""
        connection = self.connections.get(connection_id)
        if not connection:
            return
        
        connection.touch()
        
        msg_type = message.get("type", "")
        
        if msg_type == "subscribe":
            channels = message.get("channels", [])
            await self.subscribe(connection_id, channels)
        
        elif msg_type == "unsubscribe":
            channels = message.get("channels", [])
            await self.unsubscribe(connection_id, channels)
        
        elif msg_type == "ping":
            await self._send(connection, {"type": "pong"})
        
        elif msg_type == "get_state":
            await self._send_current_state(connection)
        
        else:
            logger.warning(f"Unknown message type: {msg_type}")
    
    async def _send_current_state(self, connection: WSConnection) -> None:
        """发送当前状态"""
        if not self.redis:
            await self._send(connection, {"type": "error", "message": "State not available"})
            return
        
        try:
            from services.projection_service.state_keys import ProjectionKeys
            
            state = {}
            
            dashboard = await self.redis.get_json(ProjectionKeys.dashboard_state())
            if dashboard:
                state["dashboard"] = dashboard
            
            positions = await self.redis.get_json(ProjectionKeys.position_current())
            if positions:
                state["positions"] = positions
            
            risk = await self.redis.get_json(ProjectionKeys.risk_state())
            if risk:
                state["risk"] = risk
            
            await self._send(connection, {
                "type": "current_state",
                "state": state,
            })
            
        except Exception as e:
            logger.error(f"Failed to get current state: {e}")
            await self._send(connection, {"type": "error", "message": str(e)})
    
    async def run_redis_subscriber(self) -> None:
        """运行 Redis Pub/Sub 订阅者"""
        if not self.redis:
            logger.warning("Redis not available, skipping pub/sub")
            return
        
        try:
            pubsub = self.redis.client.pubsub()
            await pubsub.subscribe(*ProjectionChannels.all())
            
            logger.info(f"Subscribed to Redis channels: {ProjectionChannels.all()}")
            
            async for message in pubsub.listen():
                if not self._running:
                    break
                
                if message["type"] == "message":
                    channel = message["channel"]
                    data = message["data"]
                    
                    try:
                        if isinstance(data, str):
                            data = json.loads(data)
                    except json.JSONDecodeError:
                        pass
                    
                    await self.broadcast(channel, data)
                    
        except Exception as e:
            logger.error(f"Redis subscriber error: {e}")
    
    @property
    def stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self._stats,
            "channels": {
                channel: len(subscribers)
                for channel, subscribers in self.channel_subscribers.items()
            },
        }


ws_gateway = WSGateway()


async def get_ws_gateway() -> WSGateway:
    """获取 WS Gateway 单例"""
    if not ws_gateway._running:
        await ws_gateway.initialize()
    return ws_gateway
