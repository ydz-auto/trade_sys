"""
Telegram Adapter - 真正的 Alpha 来源

监控：
- 新闻频道 (WuBlockchain, 金十, PANews, Odaily, TreeNews)
- KOL 群
- Alpha 群
- Whale 群

使用 Telethon 库实现
"""

import os
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set, Callable
from dataclasses import dataclass

from domain.contracts import StandardEvent, Source, EventType, Sentiment
from infrastructure.logging import get_logger

logger = get_logger("telegram.adapter")


@dataclass
class TelegramConfig:
    """Telegram 配置"""
    api_id: int = None
    api_hash: str = None
    session_name: str = "trade_agent"
    
    # 频道/群组
    channels: List[str] = None
    
    # 关键词过滤
    keywords: List[str] = None
    
    # 币种关键词
    crypto_keywords: List[str] = None
    
    def __post_init__(self):
        # 默认新闻频道
        if self.channels is None:
            self.channels = [
                "WuBlockchain",      # 币世界
                "jinse_lab",         # 金十
                "PANews",            # PANews
                "odaily",            # Odaily
                "TreeNews_CN",       # TreeNews
            ]
        
        # 默认关键词
        if self.keywords is None:
            self.keywords = [
                "BTC", "ETH", "Bitcoin", "Ethereum", "ETF",
                "BlackRock", "SEC", "FDA", "做多", "做空",
                "买入", "卖出", "看涨", "看跌", "暴涨", "暴跌"
            ]
        
        # 默认加密货币关键词
        if self.crypto_keywords is None:
            self.crypto_keywords = [
                "BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "DOT",
                "AVAX", "LINK", "MATIC", "UNI", "ATOM", "LTC", "BCH",
                "SHIB", "PEPE", "WIF", "BONK"
            ]


class TelegramAdapter:
    """Telegram 适配器
    
    使用 Telethon 库监听频道消息
    
    安装：pip install telethon
    配置：
        - 获取 API ID: https://my.telegram.org/apps
        - 获取 API Hash: 同上
    """
    
    def __init__(self, config: TelegramConfig = None):
        self.config = config or TelegramConfig()
        self.client = None
        self.is_running = False
        
        # 事件回调
        self.on_message: Optional[Callable] = None
        self.on_event: Optional[Callable] = None
        
        # 统计
        self.stats = {
            "total_messages": 0,
            "crypto_related": 0,
            "keyword_matched": 0,
            "forwarded": 0,
            "errors": 0
        }
        
        # 来源映射
        self.source_mapping = {
            "WuBlockchain": Source.JINSE.value,
            "jinse_lab": Source.JINSE.value,
            "PANews": Source.COINDESK.value,
            "odaily": Source.ODALY.value,
            "TreeNews_CN": Source.COINDESK.value,
        }
    
    def _get_source(self, channel: str) -> str:
        """获取数据源"""
        return self.source_mapping.get(channel, Source.TELEGRAM.value)
    
    async def connect(self):
        """连接 Telegram"""
        if not self.config.api_id or not self.config.api_hash:
            logger.warning("Telegram API credentials not configured. Using mock mode.")
            return False
        
        try:
            from telethon import TelegramClient
            
            self.client = TelegramClient(
                self.config.session_name,
                self.config.api_id,
                self.config.api_hash
            )
            
            await self.client.start()
            logger.info("Telegram connected successfully")
            return True
            
        except ImportError:
            logger.error("Telethon not installed. Run: pip install telethon")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to Telegram: {e}")
            return False
    
    async def disconnect(self):
        """断开连接"""
        if self.client:
            await self.client.disconnect()
            self.client = None
        logger.info("Telegram disconnected")
    
    async def listen(self):
        """监听消息"""
        if not self.client:
            connected = await self.connect()
            if not connected:
                # 使用模拟模式
                await self._mock_listen()
                return
        
        self.is_running = True
        
        try:
            # 解析频道实体
            entities = []
            for channel in self.config.channels:
                try:
                    entity = await self.client.get_entity(channel)
                    entities.append(entity)
                    logger.info(f"Joined channel: {channel}")
                except Exception as e:
                    logger.warning(f"Failed to join {channel}: {e}")
            
            # 监听新消息
            @self.client.on(events.NewMessage(chats=entities))
            async def handler(event):
                await self._handle_message(event)
            
            logger.info("Listening for messages...")
            
            while self.is_running:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Listen error: {e}")
            self.stats["errors"] += 1
    
    async def _handle_message(self, event):
        """处理消息"""
        self.stats["total_messages"] += 1
        
        try:
            message = event.message
            text = message.text or message.message or ""
            
            if not text:
                return
            
            # 获取频道信息
            chat = await event.get_chat()
            channel_name = chat.username or chat.title or "unknown"
            
            # 检查是否匹配关键词
            if not self._matches_keywords(text):
                return
            
            self.stats["keyword_matched"] += 1
            
            # 提取币种
            symbols = self._extract_symbols(text)
            
            if symbols:
                self.stats["crypto_related"] += 1
            
            # 解析情绪
            sentiment = self._parse_sentiment(text)
            
            # 创建事件
            event = StandardEvent(
                source=self._get_source(channel_name),
                event_type=EventType.NEWS.value,
                timestamp=message.date.timestamp() if message.date else datetime.now().timestamp(),
                title=f"[{channel_name}] {text[:80]}...",
                content=text[:1000],  # 限制长度
                sentiment=sentiment,
                importance=self._calculate_importance(text, symbols),
                symbols=symbols,
                tags=["telegram", channel_name],
                url=f"https://t.me/{channel_name}/{message.id}" if hasattr(message, 'id') else "",
                metadata={
                    "channel": channel_name,
                    "message_id": message.id,
                    "views": getattr(message, 'views', 0),
                    "forwards": getattr(message, 'forwards', 0),
                    "raw_text": text
                }
            )
            
            self.stats["forwarded"] += 1
            
            # 回调
            if self.on_message:
                await self.on_message(event)
            if self.on_event:
                await self.on_event(event)
                
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            self.stats["errors"] += 1
    
    def _matches_keywords(self, text: str) -> bool:
        """检查是否匹配关键词"""
        text_lower = text.lower()
        
        for keyword in self.config.keywords:
            if keyword.lower() in text_lower:
                return True
        
        for keyword in self.config.crypto_keywords:
            if keyword.lower() in text_lower:
                return True
        
        return False
    
    def _extract_symbols(self, text: str) -> List[str]:
        """提取币种符号"""
        symbols = []
        text_upper = text.upper()
        
        for keyword in self.config.crypto_keywords:
            if keyword in text_upper:
                if keyword not in symbols:
                    symbols.append(keyword)
        
        return symbols[:10]  # 最多 10 个
    
    def _parse_sentiment(self, text: str) -> str:
        """解析情绪"""
        bullish_keywords = ["涨", "多", "买入", "看涨", "做多", "暴涨", "bull", "long", "buy", "pump", "up"]
        bearish_keywords = ["跌", "空", "卖出", "看跌", "做空", "暴跌", "bear", "short", "sell", "dump", "down"]
        
        text_lower = text.lower()
        
        bullish_count = sum(1 for k in bullish_keywords if k in text_lower)
        bearish_count = sum(1 for k in bearish_keywords if k in text_lower)
        
        if bullish_count > bearish_count:
            return Sentiment.BULLISH.value
        elif bearish_count > bullish_count:
            return Sentiment.BEARISH.value
        return Sentiment.NEUTRAL.value
    
    def _calculate_importance(self, text: str, symbols: List[str]) -> float:
        """计算重要性"""
        importance = 0.5
        
        # 币种数量
        if len(symbols) >= 3:
            importance += 0.1
        
        # 关键词强度
        strong_keywords = ["ETF", "SEC", "黑天鹅", "暴涨", "暴跌", "突破", "崩盘"]
        for keyword in strong_keywords:
            if keyword in text:
                importance += 0.15
                break
        
        return min(importance, 1.0)
    
    async def _mock_listen(self):
        """模拟监听（无 API 时）"""
        self.is_running = True
        logger.info("Running in mock mode...")
        
        import random
        from datetime import datetime
        
        mock_messages = [
            ("WuBlockchain", "🔥 Bitcoin ETF 今日净流入突破 5 亿美元，BTC 突破 $70,000"),
            ("jinse_lab", "📊 ETH 升级预计下周进行，开发者社区确认时间表"),
            ("PANews", "🚀 SOL 链上活动激增，交易量创历史新高"),
            ("odaily", "📰 BlackRock 比特币 ETF 持有量突破 30 万 BTC"),
        ]
        
        while self.is_running:
            # 随机生成消息
            if random.random() > 0.7:
                channel, content = random.choice(mock_messages)
                
                event = StandardEvent(
                    source=self._get_source(channel),
                    event_type=EventType.NEWS.value,
                    timestamp=datetime.now().timestamp(),
                    title=f"[{channel}] {content[:60]}...",
                    content=content,
                    sentiment=Sentiment.BULLISH.value,
                    importance=0.7,
                    symbols=["BTC", "ETH", "SOL"],
                    tags=["telegram", "mock", channel],
                    metadata={"channel": channel, "mock": True}
                )
                
                if self.on_event:
                    await self.on_event(event)
            
            await asyncio.sleep(10)  # 每 10 秒检查一次
    
    async def stop(self):
        """停止"""
        self.is_running = False
        await self.disconnect()
    
    def get_stats(self) -> Dict:
        """获取统计"""
        return {
            **self.stats,
            "is_running": self.is_running
        }


async def demo():
    """演示"""
    print("=" * 70)
    print("Telegram 适配器演示")
    print("=" * 70)
    
    config = TelegramConfig(
        api_id=int(os.getenv("TG_API_ID", "0")) or None,
        api_hash=os.getenv("TG_API_HASH") or None
    )
    
    if not config.api_id:
        print("⚠️  未配置 API，使用模拟模式")
    
    adapter = TelegramAdapter(config)
    
    async def on_event(event: StandardEvent):
        print(f"\n📱 {event.title}")
        print(f"   Source: {event.source}")
        print(f"   Sentiment: {event.sentiment}")
        print(f"   Symbols: {event.symbols}")
    
    adapter.on_event = on_event
    
    try:
        await adapter.listen()
    except KeyboardInterrupt:
        print("\n\nStopping...")
        await adapter.stop()
        print(f"\nStats: {adapter.get_stats()}")


if __name__ == "__main__":
    asyncio.run(demo())
