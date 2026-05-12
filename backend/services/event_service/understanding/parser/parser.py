"""
Data Parser - 原始数据解析器
负责将不同来源的原始数据解析为统一格式

职责：
- 解析 News / Twitter / Telegram / RSS 等原始数据
- 提取关键字段（title, content, author, timestamp, symbols）
- 数据清洗和标准化
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from abc import ABC, abstractmethod

from infrastructure.logging import get_logger
from shared.contracts import Source

logger = get_logger("event_service.parser")


@dataclass
class ParsedContent:
    """解析后的内容"""
    title: str = ""
    content: str = ""
    author: str = ""
    source: str = ""
    source_type: str = ""
    timestamp: int = 0
    url: str = ""
    symbols: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    raw_data: Dict[str, Any] = field(default_factory=dict)


class BaseParser(ABC):
    """基础解析器"""

    @abstractmethod
    def parse(self, raw_data: Dict[str, Any]) -> ParsedContent:
        """解析原始数据"""
        pass

    def _extract_symbols(self, text: str) -> List[str]:
        """提取代币符号"""
        common_symbols = [
            "BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "AVAX", "DOGE",
            "DOT", "LINK", "MATIC", "UNI", "AAVE", "CRV", "MKR",
            "ARB", "OP", "SUI", "APT", "TIA", "INJ", "SEI",
            "FET", "RNDR", "GRT", "FIL", "NEAR", "ALGO", "VET"
        ]

        found = []
        text_upper = text.upper()

        for symbol in common_symbols:
            if symbol in text_upper:
                found.append(symbol)

        return list(set(found))


class NewsParser(BaseParser):
    """新闻解析器"""

    def parse(self, raw_data: Dict[str, Any]) -> ParsedContent:
        """解析新闻数据"""
        title = raw_data.get("title", "")
        content = raw_data.get("content", "") or raw_data.get("description", "")

        return ParsedContent(
            title=title,
            content=content,
            author=raw_data.get("author", ""),
            source=raw_data.get("source", ""),
            source_type=Source.NEWS.value,
            timestamp=raw_data.get("timestamp", 0) or int(datetime.now().timestamp()),
            url=raw_data.get("url", ""),
            symbols=self._extract_symbols(f"{title} {content}"),
            tags=raw_data.get("tags", []),
            metadata={
                "category": raw_data.get("category", ""),
                "language": raw_data.get("language", "en"),
                "sentiment": raw_data.get("sentiment", "neutral"),
            },
            raw_data=raw_data
        )


class TwitterParser(BaseParser):
    """Twitter/X 解析器"""

    def parse(self, raw_data: Dict[str, Any]) -> ParsedContent:
        """解析 Twitter 数据"""
        content = raw_data.get("content", "") or raw_data.get("text", "")
        author = raw_data.get("author", "") or raw_data.get("username", "") or raw_data.get("user", "")
        timestamp = raw_data.get("timestamp", 0)
        if not timestamp:
            created_at = raw_data.get("created_at", "")
            if created_at:
                try:
                    dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    timestamp = int(dt.timestamp())
                except Exception:
                    timestamp = int(datetime.now().timestamp())
            else:
                timestamp = int(datetime.now().timestamp())

        return ParsedContent(
            title="",
            content=content,
            author=author,
            source="twitter",
            source_type=Source.SOCIAL.value,
            timestamp=timestamp,
            url=raw_data.get("url", ""),
            symbols=self._extract_symbols(content),
            tags=raw_data.get("hashtags", []),
            metadata={
                "likes": raw_data.get("likes", 0),
                "retweets": raw_data.get("retweets", 0) or raw_data.get("retweet_count", 0),
                "followers": raw_data.get("followers", 0),
                "verified": raw_data.get("verified", False),
            },
            raw_data=raw_data
        )


class TelegramParser(BaseParser):
    """Telegram 解析器"""

    def parse(self, raw_data: Dict[str, Any]) -> ParsedContent:
        """解析 Telegram 数据"""
        content = raw_data.get("content", "") or raw_data.get("message", "")
        author = raw_data.get("author", "") or raw_data.get("sender", "")
        chat = raw_data.get("chat", {})

        return ParsedContent(
            title="",
            content=content,
            author=author,
            source=f"telegram:{chat.get('title', 'unknown')}" if isinstance(chat, dict) else "telegram",
            source_type=Source.SOCIAL.value,
            timestamp=raw_data.get("timestamp", 0) or int(datetime.now().timestamp()),
            symbols=self._extract_symbols(content),
            tags=[],
            metadata={
                "chat_id": chat.get("id") if isinstance(chat, dict) else None,
                "message_id": raw_data.get("message_id", ""),
            },
            raw_data=raw_data
        )


class EtfParser(BaseParser):
    """ETF 数据解析器"""

    def parse(self, raw_data: Dict[str, Any]) -> ParsedContent:
        """解析 ETF 数据"""
        symbol = raw_data.get("symbol", "")
        net_flow = raw_data.get("net_flow", 0)

        sentiment = "neutral"
        if net_flow > 100000000:
            sentiment = "bullish"
        elif net_flow < -100000000:
            sentiment = "bearish"

        content = f"ETF {symbol} {'inflow' if net_flow > 0 else 'outflow'}: ${net_flow / 1e6:.2f}M"

        return ParsedContent(
            title=f"ETF {symbol} Flow",
            content=content,
            source="etf_api",
            source_type=Source.ETF.value,
            timestamp=raw_data.get("timestamp", 0) or int(datetime.now().timestamp()),
            symbols=[symbol],
            metadata={
                "net_flow": net_flow,
                "aum": raw_data.get("aum", 0),
                "volume": raw_data.get("volume", 0),
                "sentiment": sentiment,
            },
            raw_data=raw_data
        )


class OnChainParser(BaseParser):
    """链上数据解析器"""

    def parse(self, raw_data: Dict[str, Any]) -> ParsedContent:
        """解析链上数据"""
        activity_type = raw_data.get("activity_type", "")
        symbol = raw_data.get("symbol", "")
        value_usd = raw_data.get("value_usd", 0)
        exchange = raw_data.get("exchange", "")

        sentiment = "neutral"
        if activity_type == "buy" or activity_type == "inflow":
            sentiment = "bullish"
        elif activity_type == "sell" or activity_type == "outflow":
            sentiment = "bearish"

        content = f"Whale {activity_type}: {value_usd / 1e6:.2f}M {symbol} on {exchange}"

        return ParsedContent(
            title=f"Whale {activity_type}",
            content=content,
            source="onchain_api",
            source_type=Source.ONCHAIN.value,
            timestamp=raw_data.get("timestamp", 0) or int(datetime.now().timestamp()),
            symbols=[symbol],
            metadata={
                "wallet": raw_data.get("wallet_address", ""),
                "amount": raw_data.get("amount", 0),
                "value_usd": value_usd,
                "exchange": exchange,
                "sentiment": sentiment,
            },
            raw_data=raw_data
        )


class DataParser:
    """统一数据解析器"""

    def __init__(self):
        self.parsers = {
            Source.NEWS.value: NewsParser(),
            "news": NewsParser(),
            "rss": NewsParser(),
            "twitter": TwitterParser(),
            "telegram": TelegramParser(),
            "etf": EtfParser(),
            "onchain": OnChainParser(),
        }

    def parse(self, raw_data: Dict[str, Any], source_type: str = "news") -> ParsedContent:
        """解析原始数据"""
        parser = self.parsers.get(source_type, NewsParser())

        try:
            return parser.parse(raw_data)
        except Exception as e:
            logger.error(f"Failed to parse {source_type} data: {e}")
            return ParsedContent(raw_data=raw_data)

    def parse_batch(self, raw_datas: List[Dict[str, Any]], source_type: str = "news") -> List[ParsedContent]:
        """批量解析"""
        return [self.parse(data, source_type) for data in raw_datas]


_parser: Optional[DataParser] = None


def get_data_parser() -> DataParser:
    """获取数据解析器"""
    global _parser
    if _parser is None:
        _parser = DataParser()
    return _parser
