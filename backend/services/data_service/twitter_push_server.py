"""
Twitter Push WebSocket Server

接收 Chrome Extension 转发的 Twitter 推送通知

架构：
Chrome Extension → WebSocket → Kafka → EventBus
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict

import websockets
from websockets.server import WebSocketServerProtocol

from shared.contracts import StandardEvent, Source, EventType, create_tweet_event
from infrastructure.logging import get_logger

logger = get_logger("twitter_push_server")

# P0 账号白名单
P0_ACCOUNTS = {
    "elonmusk", "cz_binance", "VitalikButerin", "saylor", "BarrySilbert",
    "binance", "okx", "coinbase", "EricBalchunas", "WatcherGuru", "Phyrex_Ni",
    "Saylor", "CZ_Binance", "VitalikButerin", "Phyrex_Ni"  # 大写版本
}

# 币种关键词
CRYPTO_KEYWORDS = {
    "BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "DOT", "AVAX", "LINK",
    "MATIC", "UNI", "ATOM", "LTC", "BCH", "FIL", "NEAR", "APT", "ARB", "OP",
    "SUI", "SEI", "TIA", "INJ", "FTM", "ALGO", "XLM", "VET", "ICP",
    "SHIB", "PEPE", "WIF", "BONK", "SAND", "MANA"
}


@dataclass
class PushConnection:
    """推送连接"""
    websocket: WebSocketServerProtocol
    client_id: str
    connected_at: float
    last_ping: float


class TwitterPushServer:
    """Twitter Push 通知服务器"""
    
    def __init__(self, host: str = "localhost", port: int = 8765):
        self.host = host
        self.port = port
        self.connections: Dict[str, PushConnection] = {}
        self.events: List[StandardEvent] = []
        self.max_events = 1000  # 保留最近 1000 条
        
        # 统计
        self.stats = {
            "total_received": 0,
            "total_forwarded": 0,
            "p0_filtered": 0,
            "crypto_related": 0
        }
        
    async def start(self):
        """启动服务器"""
        logger.info(f"Starting Twitter Push Server on {self.host}:{self.port}")
        
        async with websockets.serve(
            self.handle_connection,
            self.host,
            self.port,
            ping_interval=30,
            ping_timeout=10
        ):
            logger.info("Twitter Push Server started successfully")
            await asyncio.Future()  # 永久运行
    
    async def handle_connection(self, websocket: WebSocketServerProtocol, path: str):
        """处理新连接"""
        client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        connection = PushConnection(
            websocket=websocket,
            client_id=client_id,
            connected_at=datetime.now().timestamp(),
            last_ping=datetime.now().timestamp()
        )
        
        self.connections[client_id] = connection
        logger.info(f"Client connected: {client_id}")
        
        try:
            async for message in websocket:
                await self.handle_message(websocket, message, client_id)
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client disconnected: {client_id}")
        finally:
            if client_id in self.connections:
                del self.connections[client_id]
    
    async def handle_message(self, websocket: WebSocketServerProtocol, message: str, client_id: str):
        """处理消息"""
        try:
            data = json.loads(message)
            msg_type = data.get("type", "unknown")
            
            if msg_type == "ping":
                await websocket.send(json.dumps({"type": "pong", "timestamp": datetime.now().timestamp()}))
                self.connections[client_id].last_ping = datetime.now().timestamp()
                
            elif msg_type == "tweet":
                await self.process_tweet(data.get("data", {}))
                
            elif msg_type == "subscribe":
                await websocket.send(json.dumps({
                    "type": "subscribed",
                    "client_id": client_id
                }))
                
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON from {client_id}")
        except Exception as e:
            logger.error(f"Error handling message from {client_id}: {e}")
    
    async def process_tweet(self, tweet_data: Dict) -> Optional[StandardEvent]:
        """处理推文数据"""
        self.stats["total_received"] += 1
        
        author = tweet_data.get("author", "")
        content = tweet_data.get("content", "")
        
        # 检查是否是 P0 账号
        is_p0 = any(acc.lower() in author.lower() for acc in P0_ACCOUNTS)
        
        if not is_p0:
            self.stats["p0_filtered"] += 1
            logger.debug(f"P0 filtered: {author}")
            return None
        
        # 提取币种
        mentioned_symbols = tweet_data.get("mentionedSymbols", []) or []
        
        if not mentioned_symbols:
            mentioned_symbols = self._extract_crypto_symbols(content)
        
        # 检查是否与加密相关
        if not mentioned_symbols and not self._is_crypto_related(content):
            logger.debug(f"Not crypto related: {content[:50]}...")
            return None
        
        self.stats["crypto_related"] += 1
        
        # 创建标准事件
        event = create_tweet_event(
            author=author,
            content=content,
            likes=tweet_data.get("likes", 0),
            retweets=tweet_data.get("retweets", 0),
            symbols=mentioned_symbols
        )
        
        event.source = Source.TWITTER.value
        event.event_type = EventType.TWEET.value
        
        # 添加额外元数据
        event.metadata.update({
            "url": tweet_data.get("url", ""),
            "tweet_id": tweet_data.get("id", ""),
            "hashtags": tweet_data.get("hashtags", []),
            "is_p0_account": True,
            "push_source": "chrome_extension"
        })
        
        # 设置重要性
        likes = tweet_data.get("likes", 0)
        retweets = tweet_data.get("retweets", 0)
        event.importance = self._calculate_importance(likes, retweets, mentioned_symbols)
        
        # 保存事件
        self.events.append(event)
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events:]
        
        self.stats["total_forwarded"] += 1
        
        logger.info(f"Tweet processed: [{author}] {content[:50]}... (symbols: {mentioned_symbols})")
        
        # 广播到所有连接
        await self.broadcast_event(event)
        
        return event
    
    def _extract_crypto_symbols(self, text: str) -> List[str]:
        """从文本中提取币种符号"""
        symbols = []
        text_upper = text.upper()
        
        for keyword in CRYPTO_KEYWORDS:
            if keyword in text_upper:
                symbols.append(keyword)
        
        return symbols[:10]  # 最多 10 个
    
    def _is_crypto_related(self, text: str) -> bool:
        """检查是否与加密货币相关"""
        crypto_keywords = [
            "bitcoin", "ethereum", "crypto", "blockchain", "defi", "nft",
            "trading", "exchange", "wallet", "token", "coin", "binance",
            "coinbase", "layer", "protocol", "dao", "web3", "onchain"
        ]
        
        text_lower = text.lower()
        return any(kw in text_lower for kw in crypto_keywords)
    
    def _calculate_importance(self, likes: int, retweets: int, symbols: List[str]) -> float:
        """计算重要性"""
        base = 0.5
        
        # 互动量
        if likes > 10000 or retweets > 2000:
            base = 0.8
        elif likes > 1000 or retweets > 200:
            base = 0.65
        
        # 币种数量
        if len(symbols) >= 3:
            base = min(base + 0.1, 0.95)
        
        return min(base, 1.0)
    
    async def broadcast_event(self, event: StandardEvent):
        """广播事件到所有连接"""
        if not self.connections:
            return
        
        message = json.dumps({
            "type": "tweet_event",
            "event": event.to_dict()
        })
        
        disconnected = []
        
        for client_id, connection in self.connections.items():
            try:
                await connection.websocket.send(message)
            except Exception as e:
                logger.error(f"Failed to send to {client_id}: {e}")
                disconnected.append(client_id)
        
        # 清理断开的连接
        for client_id in disconnected:
            if client_id in self.connections:
                del self.connections[client_id]
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            **self.stats,
            "connections": len(self.connections),
            "events_in_memory": len(self.events)
        }
    
    def get_recent_events(self, limit: int = 50) -> List[Dict]:
        """获取最近的事件"""
        events = self.events[-limit:]
        return [e.to_dict() for e in events]


async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Twitter Push WebSocket Server")
    parser.add_argument("--host", default="localhost", help="Host to bind")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind")
    args = parser.parse_args()
    
    server = TwitterPushServer(host=args.host, port=args.port)
    
    print("""
╔══════════════════════════════════════════════════════════════╗
║            Twitter Push Notification Server                  ║
║                                                            ║
║  Waiting for Chrome Extension connections...                  ║
║  WebSocket: ws://localhost:8765                            ║
║                                                            ║
║  Install Chrome Extension:                                  ║
║  1. Open chrome://extensions/                               ║
║  2. Enable Developer Mode                                   ║
║  3. Load unpacked extension                                ║
║  4. Select frontend/extensions/twitter-push                ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    await server.start()


if __name__ == "__main__":
    asyncio.run(main())
