"""
WebSocket Manager - WebSocket连接管理
通用组件，可被各服务使用
"""

from typing import List, Dict, Any
from fastapi import WebSocket
import json

from infrastructure.logging import get_logger
logger = get_logger("websocket.manager")


class WSConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        if not self.active_connections:
            return

        message_str = json.dumps(message)

        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message_str)
            except Exception as e:
                logger.error(f"Failed to send to WebSocket: {e}")
                disconnected.append(connection)

        for conn in disconnected:
            await self.disconnect(conn)

    async def send_personal(self, websocket: WebSocket, message: Dict[str, Any]):
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send personal message: {e}")


ws_manager = WSConnectionManager()
