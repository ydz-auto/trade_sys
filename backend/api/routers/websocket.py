"""
WebSocket Router - WebSocket 端点
"""

import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from domain.logging import get_logger
from application.queries.infrastructure_queries import get_ws_gateway

logger = get_logger("ws_router")

router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket 端点
    
    客户端可以：
    1. 订阅频道：{"type": "subscribe", "channels": ["dashboard", "decision"]}
    2. 取消订阅：{"type": "unsubscribe", "channels": ["dashboard"]}
    3. 心跳：{"type": "ping"}
    4. 获取状态：{"type": "get_state"}
    """
    gateway = await get_ws_gateway()
    
    connection_id = await gateway.connect(websocket)
    
    try:
        while True:
            data = await websocket.receive_json()
            await gateway.handle_message(connection_id, data)
            
    except WebSocketDisconnect:
        logger.info(f"Client disconnected: {connection_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await gateway.disconnect(connection_id)


@router.websocket("/ws/{channel}")
async def websocket_channel(websocket: WebSocket, channel: str):
    """
    单频道 WebSocket 端点
    
    自动订阅指定频道
    """
    gateway = await get_ws_gateway()
    
    connection_id = await gateway.connect(websocket)
    
    await gateway.subscribe(connection_id, [f"channel:{channel}"])
    
    try:
        while True:
            data = await websocket.receive_json()
            await gateway.handle_message(connection_id, data)
            
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await gateway.disconnect(connection_id)
