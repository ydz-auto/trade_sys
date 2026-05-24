from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Any
import uuid


class EventType(Enum):
    PRICE_UPDATE = "price_update"
    ORDER_BOOK_UPDATE = "order_book_update"
    TRADE = "trade"

    NEWS = "news"
    TWEET = "tweet"
    REGULATORY = "regulatory"
    FUNDAMENTAL = "fundamental"
    TECHNICAL = "technical"

    ONCHAIN_TRANSFER = "onchain_transfer"
    ONCHAIN_WHALE = "onchain_whale"
    ONCHAIN_PROTOCOL = "onchain_protocol"

    PREDICTION_MARKET = "prediction_market"

    MACRO_EVENT = "macro_event"
    ETF_FLOW = "etf_flow"

    SENTIMENT_CHANGE = "sentiment_change"
    NARRATIVE_SHIFT = "narrative_shift"
    REGIME_CHANGE = "regime_change"

    UNKNOWN = "unknown"


class Sentiment(Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


class Importance(Enum):
    CRITICAL = 1.0
    HIGH = 0.75
    MEDIUM = 0.5
    LOW = 0.25


class Source(Enum):
    BINANCE = "binance"
    OKX = "okx"
    COINGECKO = "coingecko"

    COINDESK = "coindesk"
    COINTELEGRAPH = "cointelegraph"
    THEBLOCK = "theblock"
    ODALY = "odaily"
    JINSE = "jinse"
    BABI8 = "babi8"

    TWITTER = "twitter"
    REDDIT = "reddit"
    TELEGRAM = "telegram"
    QQ = "qq"

    CLAWHUB_ODAILY = "clawhub_odaily"
    CLAWHUB_PANEWS = "clawhub_panews"
    CLAWHUB_JIN10 = "clawhub_jin10"

    ETHEREUM = "ethereum"
    DEXRANK = "dexrank"
    GLASSNODE = "glassnode"

    POLYMARKET = "polymarket"

    YAHOO = "yahoo"
    CME = "cme"

    UNKNOWN = "unknown"


@dataclass
class StandardEvent:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: str = Source.UNKNOWN.value
    event_type: str = EventType.UNKNOWN.value
    timestamp: int = field(default_factory=lambda: int(datetime.now().timestamp()))
    created_at: int = field(default_factory=lambda: int(datetime.now().timestamp()))

    title: str = ""
    summary: str = ""
    content: str = ""
    url: str = ""

    importance: float = 0.5
    sentiment: str = Sentiment.UNKNOWN.value

    symbols: List[str] = field(default_factory=list)
    assets: List[str] = field(default_factory=list)

    tags: List[str] = field(default_factory=list)
    narratives: List[str] = field(default_factory=list)
    event_subtype: str = ""

    metadata: Dict[str, Any] = field(default_factory=dict)

    confidence: float = 1.0
    quality_score: float = 0.5

    original_id: str = ""
    original_url: str = ""
    original_data: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "source": self.source,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "created_at": self.created_at,
            "title": self.title,
            "summary": self.summary,
            "content": self.content,
            "url": self.url,
            "importance": self.importance,
            "sentiment": self.sentiment,
            "symbols": self.symbols,
            "assets": self.assets,
            "tags": self.tags,
            "narratives": self.narratives,
            "event_subtype": self.event_subtype,
            "metadata": self.metadata,
            "confidence": self.confidence,
            "quality_score": self.quality_score,
            "original_id": self.original_id,
            "original_url": self.original_url,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "StandardEvent":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def is_high_priority(self) -> bool:
        return self.importance >= 0.75 or self.confidence >= 0.9

    def is_bullish(self) -> bool:
        return self.sentiment == Sentiment.BULLISH.value

    def is_bearish(self) -> bool:
        return self.sentiment == Sentiment.BEARISH.value

    def get_age_seconds(self) -> int:
        return int(datetime.now().timestamp()) - self.timestamp

    def get_age_minutes(self) -> float:
        return self.get_age_seconds() / 60


class EventFilter:
    def __init__(
        self,
        event_types: List[EventType] = None,
        sources: List[Source] = None,
        symbols: List[str] = None,
        min_importance: float = 0.0,
        min_confidence: float = 0.0,
        sentiment: Sentiment = None,
        max_age_minutes: float = None
    ):
        self.event_types = event_types or []
        self.sources = sources or []
        self.symbols = symbols or []
        self.min_importance = min_importance
        self.min_confidence = min_confidence
        self.sentiment = sentiment
        self.max_age_minutes = max_age_minutes

    def matches(self, event: StandardEvent) -> bool:
        if self.event_types:
            if event.event_type not in [e.value for e in self.event_types]:
                return False

        if self.sources:
            if event.source not in [s.value for s in self.sources]:
                return False

        if self.symbols:
            if not any(s.upper() in [sym.upper() for sym in event.symbols]):
                return False

        if event.importance < self.min_importance:
            return False

        if event.confidence < self.min_confidence:
            return False

        if self.sentiment and event.sentiment != self.sentiment.value:
            return False

        if self.max_age_minutes:
            if event.get_age_minutes() > self.max_age_minutes:
                return False

        return True


def create_news_event(
    source: str,
    title: str,
    content: str,
    sentiment: str = "neutral",
    importance: float = 0.5,
    symbols: List[str] = None,
    tags: List[str] = None,
    url: str = "",
    **kwargs
) -> StandardEvent:
    return StandardEvent(
        source=source,
        event_type=EventType.NEWS.value,
        title=title,
        content=content,
        summary=content[:200] if len(content) > 200 else content,
        sentiment=sentiment,
        importance=importance,
        symbols=symbols or [],
        tags=tags or [],
        url=url,
        **kwargs
    )


def create_tweet_event(
    author: str,
    content: str,
    likes: int = 0,
    retweets: int = 0,
    symbols: List[str] = None,
    **kwargs
) -> StandardEvent:
    importance = 0.5
    if likes > 10000 or retweets > 1000:
        importance = 0.75
    if likes > 50000 or retweets > 5000:
        importance = 0.9

    return StandardEvent(
        source=Source.TWITTER.value,
        event_type=EventType.TWEET.value,
        title=f"@{author}: {content[:50]}...",
        content=content,
        importance=importance,
        symbols=symbols or [],
        metadata={
            "author": author,
            "likes": likes,
            "retweets": retweets
        },
        **kwargs
    )


def create_whale_event(
    wallet: str,
    action: str,
    symbol: str,
    amount: float,
    value_usd: float,
    exchange: str = ""
) -> StandardEvent:
    sentiment = "neutral"
    if action == "buy":
        sentiment = "bullish"
    elif action == "sell":
        sentiment = "bearish"

    importance = 0.5
    if value_usd > 1000000:
        importance = 0.75
    if value_usd > 10000000:
        importance = 0.9

    return StandardEvent(
        source=Source.CLAWHUB_ODAILY.value,
        event_type=EventType.ONCHAIN_WHALE.value,
        title=f"Whale {action}: {amount} {symbol} (${value_usd:,.0f})",
        content=f"Wallet {wallet[:10]}... {action}ed {amount} {symbol} on {exchange}",
        sentiment=sentiment,
        importance=importance,
        symbols=[symbol],
        metadata={
            "wallet": wallet,
            "action": action,
            "amount": amount,
            "value_usd": value_usd,
            "exchange": exchange
        }
    )
