"""
QQ 实时数据源 - NapCatQQ + WebSocket 方案

架构：
QQ Group → NapCatQQ → WebSocket → Python Consumer → Kafka/Redis

特点：
- 简单：不需要复杂 bot 集群
- 实时：WebSocket 推送
- 可扩展：统一事件格式

推荐技术栈：
- QQ 接入：NapCatQQ
- 协议：OneBot v11
- 消息流：WebSocket
- 后端：FastAPI / asyncio
"""

import asyncio
import json
import re
import hashlib
import random
from datetime import datetime
from typing import Dict, List, Optional, Set, Callable
from dataclasses import dataclass
import os

from domain.contracts import StandardEvent, Source, Sentiment, create_news_event
from infrastructure.logging import get_logger

logger = get_logger("qq.realtime")


@dataclass
class KeywordPriority:
    """关键词优先级配置"""
    P0_CRITICAL: List[str] = None   # SEC/ETF/爆仓/黑客
    P1_IMPORTANT: List[str] = None  # 上涨/利好/大户
    P2_NORMAL: List[str] = None     # 闲聊

    def __post_init__(self):
        self.P0_CRITICAL = [
            "SEC", "ETF", "爆仓", "hack", "黑客", "被盗", "跑路",
            "监管", "政策", "禁止", "审查", "崩盘", "暴跌", "重大",
            "liquidation", "SEC", "approval", "rejected"
        ]
        self.P1_IMPORTANT = [
            "BTC", "ETH", "SOL", "上涨", "利好", "买入", "看涨",
            "突破", "新高", "拉升", "牛市", "做多", "大户", "机构",
            "bullish", "breakout", "pump"
        ]
        self.P2_NORMAL = [
            "感觉", "好像", "可能", "大家", "聊聊", "讨论"
        ]


class QQRealtimeSource:
    """QQ 实时数据源 - 基于 WebSocket

    使用 NapCatQQ 的 WebSocket 连接获取实时消息

    配置：
    1. 安装 NapCatQQ: https://github.com/NapNeko/NapCatQQ
    2. 开启 WebSocket 服务
    3. 设置 ws_url 环境变量

    环境变量：
    - QQ_WS_URL: WebSocket 地址 (默认: ws://127.0.0.1:3001)
    - QQ_WATCH_GROUPS: 监控的群号列表 (逗号分隔)
    - QQ_ACCESS_TOKEN: NapCat 访问令牌 (可选)
    """

    def __init__(
        self,
        ws_url: str = "ws://127.0.0.1:3001",
        watch_groups: List[int] = None,
        access_token: str = None,
        use_mock: bool = None
    ):
        self.ws_url = os.getenv("QQ_WS_URL", ws_url)
        self.watch_groups = watch_groups or [
            int(g) for g in os.getenv("QQ_WATCH_GROUPS", "").split(",")
            if g.strip()
        ]
        self.access_token = access_token or os.getenv("QQ_ACCESS_TOKEN")

        if use_mock is None:
            self.use_mock = os.getenv("QQ_USE_MOCK", "true").lower() == "true"
        else:
            self.use_mock = use_mock

        self.priority = KeywordPriority()
        self._websocket = None
        self._running = False
        self._seen_messages: Set[str] = set()  # 去重
        self._dedup_window = 3600  # 去重窗口 1 小时

        # 回调
        self.on_message: Optional[Callable] = None
        self.on_event: Optional[Callable] = None

        # 统计
        self.stats = {
            "total": 0,
            "filtered": 0,
            "priority_p0": 0,
            "priority_p1": 0,
            "priority_p2": 0,
            "duplicates": 0,
            "errors": 0
        }

        logger.info(f"QQ Realtime Source initialized (ws={self.ws_url}, mock={self.use_mock})")

    def _get_dedup_key(self, msg: Dict) -> str:
        """生成去重 key"""
        content = msg.get("raw_message", "")
        user_id = msg.get("sender", {}).get("user_id", "")
        group_id = msg.get("group_id", "")

        key_str = f"{group_id}:{user_id}:{content}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def _is_duplicate(self, msg: Dict) -> bool:
        """检查是否重复"""
        key = self._get_dedup_key(msg)

        if key in self._seen_messages:
            return True

        self._seen_messages.add(key)

        if len(self._seen_messages) > 10000:
            self._seen_messages = set(list(self._seen_messages)[-5000:])

        return False

    def _get_priority(self, content: str) -> int:
        """获取消息优先级 0=P0, 1=P1, 2=P2"""
        content_lower = content.lower()

        for kw in self.priority.P0_CRITICAL:
            if kw.lower() in content_lower:
                return 0

        for kw in self.priority.P1_IMPORTANT:
            if kw.lower() in content_lower:
                return 1

        return 2

    def _extract_symbols(self, content: str) -> List[str]:
        """提取币种"""
        symbols = []

        patterns = [
            r'\bBTC\b', r'\bETH\b', r'\bSOL\b', r'\bBNB\b',
            r'\bXRP\b', r'\bADA\b', r'\bDOGE\b', r'\bDOT\b',
            r'\bAVAX\b', r'\bLINK\b', r'\bMATIC\b', r'\bUNI\b',
            r'\bATOM\b', r'\bLTC\b', r'\bBCH\b', r'\bSHIB\b',
            r'\bPEPE\b', r'\bWIF\b', r'\bBONK\b', r'\bSUI\b'
        ]

        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if match.upper() not in symbols:
                    symbols.append(match.upper())

        return symbols[:5]

    def _parse_sentiment(self, content: str) -> str:
        """解析情绪"""
        bullish = ["涨", "多", "买入", "看涨", "做多", "暴涨", "拉升", "利好"]
        bearish = ["跌", "空", "卖出", "看跌", "做空", "暴跌", "砸盘", "利空"]

        bullish_count = sum(1 for w in bullish if w in content)
        bearish_count = sum(1 for w in bearish if w in content)

        if bullish_count > bearish_count:
            return Sentiment.BULLISH.value
        elif bearish_count > bullish_count:
            return Sentiment.BEARISH.value
        return Sentiment.NEUTRAL.value

    def _to_standard_event(self, msg: Dict, priority: int) -> StandardEvent:
        """转换为标准事件"""
        content = msg.get("raw_message", "")
        group_id = msg.get("group_id", "")
        sender = msg.get("sender", {})
        user_id = sender.get("user_id", "unknown")
        nickname = sender.get("nickname", "匿名")

        symbols = self._extract_symbols(content)
        sentiment = self._parse_sentiment(content)

        priority_labels = {0: "P0", 1: "P1", 2: "P2"}
        priority_label = priority_labels.get(priority, "P2")

        importance_map = {0: 0.95, 1: 0.7, 2: 0.4}

        event = create_news_event(
            source=Source.QQ.value,
            title=f"[{priority_label} {group_id}] {nickname}",
            content=content[:500],
            sentiment=sentiment,
            importance=importance_map.get(priority, 0.4),
            symbols=symbols,
            tags=["qq", f"priority_{priority_label}"]
        )

        event.metadata = {
            "platform": "qq",
            "group_id": group_id,
            "user_id": user_id,
            "sender": nickname,
            "message_id": msg.get("message_id"),
            "priority": priority_label,
            "raw_msg": msg
        }

        return event

    async def connect(self):
        """连接到 NapCatQQ WebSocket"""
        import websockets

        try:
            logger.info(f"正在连接 NapCatQQ: {self.ws_url}")

            self._websocket = await websockets.connect(
                self.ws_url,
                extra_headers={"Authorization": f"Bearer {self.access_token}"}
                if self.access_token else {}
            )
            logger.info(f"✅ 已连接到 NapCatQQ")
            return True
        except Exception as e:
            logger.error(f"❌ 连接失败: {e}")
            logger.error("提示: 请确保 NapCatQQ 已启动并且 WebSocket 服务已开启")
            logger.error("NapCatQQ 下载: https://github.com/NapNeko/NapCatQQ/releases")
            return False

    async def listen(self):
        """监听消息"""
        self._running = True

        if self.use_mock:
            await self._mock_listen()
        else:
            await self._real_listen()

    async def _real_listen(self):
        """真实模式：连接 NapCatQQ"""
        import websockets

        while self._running:
            try:
                if not self._websocket:
                    if not await self.connect():
                        await asyncio.sleep(5)
                        continue

                async for msg_text in self._websocket:
                    try:
                        msg = json.loads(msg_text)
                        await self._handle_message(msg)
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON: {msg_text[:100]}")
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
                        self.stats["errors"] += 1

            except websockets.exceptions.ConnectionClosed:
                logger.warning("WebSocket disconnected, reconnecting...")
                self._websocket = None
                await asyncio.sleep(3)
            except Exception as e:
                logger.error(f"Listen error: {e}")
                self.stats["errors"] += 1
                await asyncio.sleep(5)

    async def _mock_listen(self):
        """模拟模式：生成测试数据"""
        logger.info("Running in MOCK mode")

        mock_messages = [
            {
                "post_type": "message",
                "message_type": "group",
                "group_id": 123456789,
                "message_id": 1001,
                "sender": {"user_id": 666666, "nickname": "小韭菜"},
                "raw_message": "今天 BTC 突破 70000 了！太猛了！",
                "time": int(datetime.now().timestamp())
            },
            {
                "post_type": "message",
                "message_type": "group",
                "group_id": 123456789,
                "message_id": 1002,
                "sender": {"user_id": 777777, "nickname": "合约大佬"},
                "raw_message": "SEC 批准 BTC ETF 了！重大利好！",
                "time": int(datetime.now().timestamp())
            },
            {
                "post_type": "message",
                "message_type": "group",
                "group_id": 987654321,
                "message_id": 1003,
                "sender": {"user_id": 888888, "nickname": "链上分析师"},
                "raw_message": "ETH 也跟上了，准备做多。",
                "time": int(datetime.now().timestamp())
            },
            {
                "post_type": "message",
                "message_type": "group",
                "group_id": 123456789,
                "message_id": 1004,
                "sender": {"user_id": 999999, "nickname": "风险提醒"},
                "raw_message": "注意风险，现在点位有点高了",
                "time": int(datetime.now().timestamp())
            },
            {
                "post_type": "message",
                "message_type": "group",
                "group_id": 987654321,
                "message_id": 1005,
                "sender": {"user_id": 111111, "nickname": "DeFi 研究"},
                "raw_message": "SOL 生态最近很活跃",
                "time": int(datetime.now().timestamp())
            }
        ]

        msg_index = 0
        while self._running:
            msg = mock_messages[msg_index % len(mock_messages)]
            msg_index += 1

            await self._handle_message(msg)
            await asyncio.sleep(random.uniform(2, 5))

    async def _handle_message(self, msg: Dict):
        """处理收到的消息"""
        if msg.get("post_type") != "message":
            return

        if msg.get("message_type") != "group":
            return

        group_id = msg.get("group_id")

        if self.watch_groups and group_id not in self.watch_groups:
            return

        content = msg.get("raw_message", "").strip()
        if not content:
            return

        self.stats["total"] += 1

        if self._is_duplicate(msg):
            self.stats["duplicates"] += 1
            return

        priority = self._get_priority(content)

        if priority == 0:
            self.stats["priority_p0"] += 1
        elif priority == 1:
            self.stats["priority_p1"] += 1
        else:
            self.stats["priority_p2"] += 1
            self.stats["filtered"] += 1

        event = self._to_standard_event(msg, priority)

        if self.on_message:
            await self.on_message(event)

        if self.on_event:
            await self.on_event(event)

        if priority == 0:
            logger.info(f"[P0] {event.title}: {event.content[:50]}")

    async def stop(self):
        """停止监听"""
        self._running = False
        if self._websocket:
            await self._websocket.close()
        logger.info("QQ Realtime Source stopped")

    def get_stats(self) -> Dict:
        """获取统计"""
        return {
            **self.stats,
            "cache_size": len(self._seen_messages)
        }


async def demo():
    """演示"""
    print("=" * 70)
    print("QQ 实时数据源演示")
    print("=" * 70)
    print("\n注意：需要先安装 NapCatQQ 并开启 WebSocket")
    print("或者设置 QQ_USE_MOCK=true 使用模拟数据\n")

    source = QQRealtimeSource()

    async def on_event(event):
        print(f"\n📱 [{event.metadata['priority']}] {event.title}")
        print(f"   {event.content[:80]}...")
        print(f"   币种: {event.symbols} | 情绪: {event.sentiment}")

    source.on_event = on_event

    try:
        await source.listen()
    except KeyboardInterrupt:
        print("\n\n停止中...")
        await source.stop()
        print(f"\n统计: {source.get_stats()}")


if __name__ == "__main__":
    asyncio.run(demo())
