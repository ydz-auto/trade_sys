"""
Standard Event Protocol - 标准事件协议（系统共享合约）

这是系统的核心公共语言，所有跨服务通信都使用这个协议。
这个协议必须保持稳定，所有变更需要版本管理。

所有外部数据源（Skill/API/Crawler）都必须转换为标准事件格式。
这确保：
- 统一的事件格式
- 易于切换数据源
- 支持回测和 replay
- 多 Agent/多模型兼容

事件流向：
Skill/API/Crawler → Adapter → Normalization → StandardEvent → EventBus
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
import uuid


class EventType(Enum):
    """事件类型"""
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
    """情绪方向"""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


class Importance(Enum):
    """重要性级别"""
    CRITICAL = 1.0
    HIGH = 0.75
    MEDIUM = 0.5
    LOW = 0.25


class Source(Enum):
    """数据源"""
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
    """标准事件 - 所有数据源的统一输出格式（系统共享合约）

    这是系统的核心公共语言，所有 Adapter 都应该输出这个格式。

    事件流向：
    External Source → Adapter → StandardEvent → EventBus → Consumers
    """

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
    """事件过滤器"""

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


class CanonicalSymbol(str, Enum):
    """统一标的符号"""
    BTC = "BTC"
    ETH = "ETH"
    SOL = "SOL"
    BNB = "BNB"
    XRP = "XRP"
    ADA = "ADA"
    AVAX = "AVAX"
    DOGE = "DOGE"
    DOT = "DOT"
    LINK = "LINK"


class Exchange(str, Enum):
    """交易所"""
    BINANCE = "binance"
    OKX = "okx"
    COINBASE = "coinbase"
    KRAKEN = "kraken"
    BYBIT = "bybit"


class Timeframe(str, Enum):
    """时间周期 - 系统唯一标准"""
    S1 = "1s"
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"

    @property
    def seconds(self) -> int:
        mapping = {
            "1s": 1,
            "1m": 60,
            "5m": 300,
            "15m": 900,
            "30m": 1800,
            "1h": 3600,
            "4h": 14400,
            "1d": 86400,
            "1w": 604800,
        }
        return mapping.get(self.value, 60)

    @classmethod
    def from_string(cls, tf: str) -> "Timeframe":
        return cls(tf)


@dataclass
class Candle:
    """K线数据 - 系统唯一标准"""
    symbol: str
    exchange: Exchange
    timeframe: Timeframe
    open_time: int
    close_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float = 0.0
    trade_count: int = 0
    is_closed: bool = True
    source: str = "aggregated"
    event_time: int = field(default_factory=lambda: int(datetime.now().timestamp() * 1000))
    is_complete: bool = True
    missing_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def canonical_symbol(self) -> str:
        return self.symbol.upper().replace("USDT", "").replace("USD", "")

    def get_bucket(self) -> int:
        return self.open_time - (self.open_time % (self.timeframe.seconds * 1000))

    def is_bullish(self) -> bool:
        return self.close > self.open

    def is_bearish(self) -> bool:
        return self.close < self.open

    def get_body(self) -> float:
        return abs(self.close - self.open)

    def get_range(self) -> float:
        return self.high - self.low

    def get_upper_shadow(self) -> float:
        return self.high - max(self.open, self.close)

    def get_lower_shadow(self) -> float:
        return min(self.open, self.close) - self.low

    def to_dict(self) -> Dict:
        return {
            "exchange": self.exchange.value if isinstance(self.exchange, Exchange) else self.exchange,
            "symbol": self.symbol,
            "timeframe": self.timeframe.value if isinstance(self.timeframe, Timeframe) else self.timeframe,
            "open_time": self.open_time,
            "close_time": self.close_time,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "quote_volume": self.quote_volume,
            "trade_count": self.trade_count,
            "is_closed": self.is_closed,
            "source": self.source,
            "event_time": self.event_time,
            "is_complete": self.is_complete,
            "missing_count": self.missing_count,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Candle":
        return cls(
            exchange=data.get("exchange", "binance") if isinstance(data.get("exchange"), str) else Exchange(data.get("exchange", "binance")),
            symbol=data["symbol"],
            timeframe=Timeframe(data["timeframe"]) if isinstance(data["timeframe"], str) else data["timeframe"],
            open_time=data["open_time"],
            close_time=data.get("close_time", data["open_time"] + data.get("timeframe", 60000)),
            open=float(data["open"]),
            high=float(data["high"]),
            low=float(data["low"]),
            close=float(data["close"]),
            volume=float(data["volume"]),
            quote_volume=float(data.get("quote_volume", 0)),
            trade_count=int(data.get("trade_count", 0)),
            is_closed=data.get("is_closed", True),
            source=data.get("source", "aggregated"),
            event_time=data.get("event_time", int(datetime.now().timestamp() * 1000)),
        )

    def to_clickhouse_row(self) -> Dict:
        return {
            "exchange": self.exchange.value if isinstance(self.exchange, Exchange) else self.exchange,
            "symbol": self.symbol,
            "timeframe": self.timeframe.value if isinstance(self.timeframe, Timeframe) else self.timeframe,
            "open_time": self.open_time,
            "open_time_dt": datetime.fromtimestamp(self.open_time / 1000),
            "close_time": self.close_time,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "quote_volume": self.quote_volume,
            "trade_count": self.trade_count,
            "is_closed": 1 if self.is_closed else 0,
            "is_complete": 1 if self.is_complete else 0,
            "missing_count": self.missing_count,
        }


@dataclass
class Trade:
    """成交数据 - 系统唯一标准"""
    symbol: str
    exchange: Exchange
    timestamp: int
    price: float
    quantity: float
    quote_quantity: float
    is_buyer_maker: bool
    trade_id: str = ""

    @property
    def side(self) -> str:
        return "sell" if self.is_buyer_maker else "buy"

    @property
    def canonical_symbol(self) -> str:
        return self.symbol.upper().replace("USDT", "").replace("USD", "")

    def to_dict(self) -> Dict:
        return {
            "exchange": self.exchange.value if isinstance(self.exchange, Exchange) else self.exchange,
            "symbol": self.symbol,
            "trade_id": self.trade_id,
            "price": self.price,
            "quantity": self.quantity,
            "quote_quantity": self.quote_quantity,
            "timestamp": self.timestamp,
            "is_buyer_maker": self.is_buyer_maker,
            "side": self.side,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Trade":
        return cls(
            exchange=data.get("exchange", "binance") if isinstance(data.get("exchange"), str) else Exchange(data.get("exchange", "binance")),
            symbol=data["symbol"],
            trade_id=data.get("trade_id", ""),
            price=float(data["price"]),
            quantity=float(data["quantity"]),
            quote_quantity=float(data.get("quote_quantity", 0)),
            timestamp=int(data["timestamp"]),
            is_buyer_maker=bool(data.get("is_buyer_maker", False)),
        )


@dataclass
class OrderBookLevel:
    """订单簿级别"""
    price: float
    quantity: float


@dataclass
class OrderBook:
    """订单簿数据 - 系统唯一标准"""
    symbol: str
    exchange: Exchange
    timestamp: int
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]

    def get_mid_price(self) -> float:
        if not self.bids or not self.asks:
            return 0.0
        return (self.bids[0].price + self.asks[0].price) / 2

    def get_spread(self) -> float:
        if not self.bids or not self.asks:
            return 0.0
        return self.asks[0].price - self.bids[0].price

    def get_imbalance(self) -> float:
        if not self.bids or not self.asks:
            return 0.0
        bid_vol = sum(b.quantity for b in self.bids[:10])
        ask_vol = sum(a.quantity for a in self.asks[:10])
        total = bid_vol + ask_vol
        if total == 0:
            return 0.0
        return (bid_vol - ask_vol) / total


@dataclass
class MarketEvent:
    """市场事件 - 用于 fusion_service"""
    symbol: str
    exchange: Exchange
    event_type: str
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: int = field(default_factory=lambda: int(datetime.now().timestamp()))
    price: float = 0.0
    volume: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Signal:
    """交易信号 - fusion_service 输出"""
    symbol: str
    direction: str
    strength: float
    confidence: float
    source: str
    signal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: int = field(default_factory=lambda: int(datetime.now().timestamp()))
    expires_at: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return int(datetime.now().timestamp()) > self.expires_at

    def to_dict(self) -> Dict:
        return {
            "signal_id": self.signal_id,
            "symbol": self.symbol,
            "direction": self.direction,
            "strength": self.strength,
            "confidence": self.confidence,
            "source": self.source,
            "timestamp": self.timestamp,
            "expires_at": self.expires_at,
            "metadata": self.metadata
        }
