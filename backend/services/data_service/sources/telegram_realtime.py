"""
Telegram 实时数据源 - Telethon + 频道监听

架构：
Telegram Channels → Telethon → Python Consumer → Kafka/Redis

特点：
- 监控优质新闻频道 (WuBlockchain, 金十, PANews 等)
- 关键词优先级过滤 P0/P1/P2
- 消息标准化
- 去重机制

推荐配置：
- API 获取: https://my.telegram.org/apps
- 库: Telethon
"""

import asyncio
import hashlib
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Set, Callable

from domain.contracts import StandardEvent, Source, Sentiment, create_news_event
from infrastructure.logging import get_logger

logger = get_logger("telegram.realtime")


class TelegramRealtimeSource:
    """Telegram 实时数据源

    监控的优质频道：
    - WuBlockchain (币世界)
    - 金十数据 (jinse_lab)
    - PANews
    - Odaily
    - TreeNews

    配置：
    1. 获取 API: https://my.telegram.org/apps
    2. pip install telethon
    3. 设置环境变量

    环境变量：
    - TELEGRAM_API_ID: API ID
    - TELEGRAM_API_HASH: API Hash
    - TELEGRAM_PHONE: 手机号
    - TELEGRAM_SESSION: Session 名称 (可选)
    - TELEGRAM_CHANNELS: 监控的频道用户名 (逗号分隔)
    """

    DEFAULT_CHANNELS = [
        "WuBlockchain",      # 币世界
        "jinse_lab",         # 金十
        "PANews",            # PANews
        "odaily",            # Odaily
        "TreeNews_CN",       # TreeNews
        "CoinMarketCap",     # CMC
        "CryptoCompare",     # 加密对比
    ]

    def __init__(
        self,
        api_id: int = None,
        api_hash: str = None,
        phone: str = None,
        channels: List[str] = None,
        use_mock: bool = None
    ):
        self.api_id = api_id or int(os.getenv("TELEGRAM_API_ID", "0"))
        self.api_hash = api_hash or os.getenv("TELEGRAM_API_HASH", "")
        self.phone = phone or os.getenv("TELEGRAM_PHONE", "")

        if use_mock is None:
            self.use_mock = os.getenv("TELEGRAM_USE_MOCK", "true").lower() == "true"
        else:
            self.use_mock = use_mock

        # 如果没有配置 API，默认使用模拟模式
        if not self.api_id or not self.api_hash:
            self.use_mock = True
            logger.warning("Telegram API not configured, using mock mode")

        self.channels = channels or [
            c.strip() for c in os.getenv("TELEGRAM_CHANNELS", "").split(",")
            if c.strip()
        ] or self.DEFAULT_CHANNELS

        self._client = None
        self._running = False
        self._seen_messages: Set[str] = set()

        # 关键词优先级
        self.p0_keywords = [
            "SEC", "ETF", "approval", "approved", "rejected",
            "爆仓", "hack", "被盗", "跑路", "监管", "政策",
            "崩盘", "暴跌", "暴涨", "liquidation", "FTX", "Binance"
        ]
        self.p1_keywords = [
            "BTC", "ETH", "SOL", "上涨", "利好", "买入", "突破",
            "bullish", "breakout", "pump", "做多", "牛市", "ETF"
        ]
        self.p2_keywords = [
            "分析", "觉得", "可能", "讨论", "看看"
        ]

        # 回调
        self.on_message: Optional[Callable] = None
        self.on_event: Optional[Callable] = None

        # 统计
        self.stats = {
            "total": 0,
            "p0": 0,
            "p1": 0,
            "p2": 0,
            "duplicates": 0,
            "errors": 0
        }

        logger.info(f"Telegram Realtime Source initialized (mock={self.use_mock})")

    def _get_priority(self, content: str) -> int:
        """获取优先级 0=P0, 1=P1, 2=P2"""
        content_lower = content.lower()

        for kw in self.p0_keywords:
            if kw.lower() in content_lower:
                return 0

        for kw in self.p1_keywords:
            if kw.lower() in content_lower:
                return 1

        return 2

    def _extract_symbols(self, content: str) -> List[str]:
        """提取币种"""
        symbols = []
        patterns = [
            r'\bBTC\b', r'\bETH\b', r'\bSOL\b', r'\bBNB\b', r'\bXRP\b',
            r'\bADA\b', r'\bDOGE\b', r'\bDOT\b', r'\bAVAX\b', r'\bLINK\b',
            r'\bMATIC\b', r'\bUNI\b', r'\bATOM\b', r'\bLTC\b', r'\bBCH\b'
        ]

        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if match.upper() not in symbols:
                    symbols.append(match.upper())

        return symbols[:5]

    def _parse_sentiment(self, content: str) -> str:
        """解析情绪"""
        bullish = ["涨", "多", "买入", "看涨", "做多", "暴涨", "拉升", "利好", "bullish"]
        bearish = ["跌", "空", "卖出", "看跌", "做空", "暴跌", "砸盘", "利空", "bearish"]

        bullish_count = sum(1 for w in bullish if w in content.lower())
        bearish_count = sum(1 for w in bearish if w in content.lower())

        if bullish_count > bearish_count:
            return Sentiment.BULLISH.value
        elif bearish_count > bullish_count:
            return Sentiment.BEARISH.value
        return Sentiment.NEUTRAL.value

    def _is_duplicate(self, msg_id: int, channel: str) -> bool:
        """检查重复"""
        key = f"{channel}:{msg_id}"
        if key in self._seen_messages:
            return True
        self._seen_messages.add(key)

        if len(self._seen_messages) > 5000:
            self._seen_messages = set(list(self._seen_messages)[-2500:])

        return False

    def _to_event(self, msg: Dict, channel: str, priority: int) -> StandardEvent:
        """转换为标准事件"""
        content = msg.get("content", "")
        msg_id = msg.get("id", 0)
        sender = msg.get("sender", "unknown")
        timestamp = msg.get("timestamp", int(datetime.now().timestamp()))

        symbols = self._extract_symbols(content)
        sentiment = self._parse_sentiment(content)

        priority_labels = {0: "P0", 1: "P1", 2: "P2"}
        importance_map = {0: 0.95, 1: 0.7, 2: 0.4}

        event = create_news_event(
            source=Source.TELEGRAM.value,
            title=f"[{priority_labels[priority]} {channel}] {sender}",
            content=content[:500],
            sentiment=sentiment,
            importance=importance_map.get(priority, 0.4),
            symbols=symbols,
            tags=["telegram", f"priority_{priority_labels[priority]}", channel]
        )

        event.metadata = {
            "platform": "telegram",
            "channel": channel,
            "channel_title": msg.get("channel_title", channel),
            "msg_id": msg_id,
            "sender": sender,
            "priority": priority_labels[priority],
            "raw_msg": msg
        }
        event.timestamp = timestamp

        return event

    async def connect(self) -> bool:
        """连接 Telegram"""
        if self.use_mock:
            return True

        try:
            from telethon import TelegramClient

            session_name = os.getenv("TELEGRAM_SESSION", "trade_agent")
            self._client = TelegramClient(session_name, self.api_id, self.api_hash)

            await self._client.start(phone=self.phone)
            logger.info("✅ Telegram connected")
            return True

        except ImportError:
            logger.error("Telethon not installed: pip install telethon")
            return False
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False

    async def listen(self):
        """监听消息"""
        self._running = True

        if self.use_mock:
            await self._mock_listen()
        else:
            await self._real_listen()

    async def _real_listen(self):
        """真实模式"""
        if not self._client:
            if not await self.connect():
                return

        logger.info(f"Listening to channels: {self.channels}")

        try:
            async for dialog in self._client.iter_dialogs():
                if dialog.entity.username in self.channels:
                    logger.info(f"Monitoring: {dialog.name} (@{dialog.entity.username})")

            @self._client.on()
            async def handler(event):
                msg = event.message
                channel = event.chat.username if event.chat else "unknown"

                if channel not in self.channels:
                    return

                content = msg.text or msg.message or ""
                if not content:
                    return

                self.stats["total"] += 1

                if self._is_duplicate(msg.id, channel):
                    self.stats["duplicates"] += 1
                    return

                priority = self._get_priority(content)

                if priority == 0:
                    self.stats["p0"] += 1
                elif priority == 1:
                    self.stats["p1"] += 1
                else:
                    self.stats["p2"] += 1

                msg_dict = {
                    "id": msg.id,
                    "content": content,
                    "sender": msg.sender.username if msg.sender else "unknown",
                    "timestamp": msg.date.timestamp() if msg.date else 0
                }

                event = self._to_event(msg_dict, channel, priority)

                if self.on_message:
                    await self.on_message(event)
                if self.on_event:
                    await self.on_event(event)

                if priority == 0:
                    logger.info(f"[P0] {channel}: {content[:50]}")

            await self._client.run_until_disconnected()

        except Exception as e:
            logger.error(f"Listen error: {e}")
            self.stats["errors"] += 1

    async def _mock_listen(self):
        """模拟模式"""
        logger.info("Running in MOCK mode")

        import random

        mock_messages = [
            {
                "id": 1001,
                "channel": "WuBlockchain",
                "content": "Binance 获得迪拜加密牌照，重大利好！",
                "sender": "WuBlockchain",
                "timestamp": int(datetime.now().timestamp())
            },
            {
                "id": 1002,
                "channel": "jinse_lab",
                "content": "BTC 突破 70000 关口，ETH 跟随上涨",
                "sender": "金十数据",
                "timestamp": int(datetime.now().timestamp())
            },
            {
                "id": 1003,
                "channel": "PANews",
                "content": "SEC 主席发言：对 ETF 持开放态度",
                "sender": "PANews",
                "timestamp": int(datetime.now().timestamp())
            }
        ]

        idx = 0
        while self._running:
            msg = mock_messages[idx % len(mock_messages)]
            idx += 1

            priority = self._get_priority(msg["content"])

            if priority == 0:
                self.stats["p0"] += 1
            elif priority == 1:
                self.stats["p1"] += 1
            else:
                self.stats["p2"] += 1

            self.stats["total"] += 1

            event = self._to_event(msg, msg["channel"], priority)

            if self.on_message:
                await self.on_message(event)
            if self.on_event:
                await self.on_event(event)

            logger.info(f"[{'P0' if priority == 0 else 'P1' if priority == 1 else 'P2'}] {msg['channel']}: {msg['content'][:50]}")

            await asyncio.sleep(random.uniform(3, 8))

    async def stop(self):
        """停止"""
        self._running = False
        if self._client:
            await self._client.disconnect()
        logger.info("Telegram Source stopped")

    def get_stats(self) -> Dict:
        """获取统计"""
        return {
            **self.stats,
            "cache_size": len(self._seen_messages)
        }
