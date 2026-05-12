"""
实时数据源基类

统一架构：
- QQ (NapCatQQ)
- Telegram (Telethon)
- Twitter (WebSocket)
- ...

共享能力：
- 关键词优先级过滤
- 消息标准化
- 去重机制
- 情绪分析
- 币种抽取
- 模拟模式
- 回调接口
"""

import asyncio
import re
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Set, Callable

from shared.contracts import StandardEvent, Source, Sentiment, create_news_event
from infrastructure.logging import get_logger


class Priority:
    """消息优先级"""
    P0_CRITICAL = "P0"   # 重要 (🔴)
    P1_IMPORTANT = "P1"  # 关注 (🟡)
    P2_NORMAL = "P2"      # 普通 (🟢)


class BaseSource(ABC):
    """实时数据源基类

    子类需要实现：
    - connect() - 连接数据源
    - listen() - 开始监听
    - stop() - 停止
    - get_stats() - 获取统计

    共享能力：
    - 关键词优先级过滤
    - 去重机制
    - 消息标准化
    - 模拟模式
    - 回调接口
    """

    def __init__(self, name: str, source: Source, use_mock: bool = False):
        self.name = name
        self.source = source
        self.use_mock = use_mock

        self.logger = get_logger(f"source.{name}")

        # 回调
        self.on_event: Optional[Callable[[StandardEvent], None]] = None
        self.on_raw: Optional[Callable[[Dict], None]] = None

        # 统计
        self.stats = {
            "total": 0,
            "p0": 0,
            "p1": 0,
            "p2": 0,
            "duplicates": 0,
            "errors": 0,
            "start_time": datetime.now(),
        }

        # 去重
        self._seen: Set[str] = set()
        self._max_seen = 10000  # 最多记录 1w 条

        # 默认关键词
        self.p0_keywords = [
            "SEC", "ETF", "approval", "approved", "rejected",
            "爆仓", "hack", "被盗", "跑路", "监管", "政策",
            "崩盘", "暴跌", "暴涨", "liquidation", "FTX", "Binance"
        ]

        self.p1_keywords = [
            "BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE",
            "上涨", "利好", "买入", "看涨", "突破", "新高",
            "bullish", "breakout", "pump", "做多", "牛市"
        ]

        self.p2_keywords = [
            "闲聊", "讨论", "看看", "感觉", "可能"
        ]

    def set_keywords(self, p0: List[str] = None, p1: List[str] = None, p2: List[str] = None):
        """设置关键词"""
        if p0:
            self.p0_keywords = p0
        if p1:
            self.p1_keywords = p1
        if p2:
            self.p2_keywords = p2

    def get_priority(self, content: str) -> str:
        """获取优先级"""
        if not content:
            return Priority.P2_NORMAL

        content_lower = content.lower()

        for kw in self.p0_keywords:
            if kw.lower() in content_lower:
                return Priority.P0_CRITICAL

        for kw in self.p1_keywords:
            if kw.lower() in content_lower:
                return Priority.P1_IMPORTANT

        return Priority.P2_NORMAL

    def extract_symbols(self, content: str) -> List[str]:
        """提取币种"""
        if not content:
            return []

        symbols = []

        # 常用币种正则 (不区分大小写)
        patterns = [
            r"\bBTC\b", r"\bETH\b", r"\bSOL\b", r"\bBNB\b", r"\bXRP\b",
            r"\bADA\b", r"\bDOGE\b", r"\bDOT\b", r"\bAVAX\b", r"\bLINK\b",
            r"\bMATIC\b", r"\bUNI\b", r"\bATOM\b", r"\bLTC\b", r"\bBCH\b"
        ]

        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                symbol_upper = match.upper()
                if symbol_upper not in symbols:
                    symbols.append(symbol_upper)

        return symbols[:5]  # 最多返回 5 个

    def analyze_sentiment(self, content: str) -> Sentiment:
        """简单情绪分析"""
        if not content:
            return Sentiment.NEUTRAL

        bullish = ["涨", "多", "买入", "看涨", "做多", "暴涨", "拉升", "利好", "bullish", "pump", "breakout"]
        bearish = ["跌", "空", "卖出", "看跌", "做空", "暴跌", "砸盘", "利空", "bearish", "dump", "crash"]

        bullish_count = sum(1 for w in bullish if w in content.lower())
        bearish_count = sum(1 for w in bearish if w in content.lower())

        if bullish_count > bearish_count:
            return Sentiment.BULLISH
        elif bearish_count > bullish_count:
            return Sentiment.BEARISH

        return Sentiment.NEUTRAL

    def get_importance_score(self, priority: str) -> float:
        """获取重要性分数"""
        if priority == Priority.P0_CRITICAL:
            return 0.9
        elif priority == Priority.P1_IMPORTANT:
            return 0.7
        else:
            return 0.4

    def is_duplicate(self, msg_id: str) -> bool:
        """检查重复"""
        if msg_id in self._seen:
            return True

        self._seen.add(msg_id)

        # 自动清理
        if len(self._seen) > self._max_seen:
            self._seen = set(list(self._seen)[-5000:])  # 保留最新的 5000 条

        return False

    def build_event(
        self,
        content: str,
        priority: str,
        channel: Optional[str] = None,
        sender: Optional[str] = None,
        extra_metadata: Optional[Dict] = None,
        title: Optional[str] = None
    ) -> StandardEvent:
        """构建标准事件"""
        symbols = self.extract_symbols(content)
        sentiment = self.analyze_sentiment(content)
        importance = self.get_importance_score(priority)

        if not title:
            title = f"[{priority}] {self.name}"

        event = create_news_event(
            source=self.source,
            title=title,
            content=content,
            sentiment=sentiment,
            importance=importance,
            symbols=symbols,
            tags=[priority, self.name]
        )

        # 元数据
        metadata = {
            "platform": self.name,
            "priority": priority,
        }
        if channel:
            metadata["channel"] = channel
        if sender:
            metadata["sender"] = sender
        if extra_metadata:
            metadata.update(extra_metadata)

        event.metadata = metadata
        return event

    async def emit_event(self, event: StandardEvent):
        """发射事件"""
        if self.on_event:
            if asyncio.iscoroutinefunction(self.on_event):
                await self.on_event(event)
            else:
                self.on_event(event)

    async def emit_raw(self, raw: Dict):
        """发射原始数据"""
        if self.on_raw:
            if asyncio.iscoroutinefunction(self.on_raw):
                await self.on_raw(raw)
            else:
                self.on_raw(raw)

    def log_received(self, priority: str, content: str):
        """记录收到"""
        self.stats["total"] += 1
        if priority == Priority.P0_CRITICAL:
            self.stats["p0"] += 1
        elif priority == Priority.P1_IMPORTANT:
            self.stats["p1"] += 1
        else:
            self.stats["p2"] += 1

    def log_duplicate(self):
        """记录重复"""
        self.stats["duplicates"] += 1

    def log_error(self):
        """记录错误"""
        self.stats["errors"] += 1

    def get_stats(self) -> Dict:
        """获取统计"""
        uptime = (datetime.now() - self.stats["start_time"]).total_seconds()
        return {
            **self.stats,
            "uptime_seconds": uptime,
            "seen_count": len(self._seen),
        }

    @abstractmethod
    async def connect(self) -> bool:
        """连接数据源 (可选)"""
        pass

    @abstractmethod
    async def listen(self):
        """开始监听 (阻塞)"""
        pass

    @abstractmethod
    async def stop(self):
        """停止"""
        pass
