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
    # 市场事件
    PRICE_UPDATE = "price_update"
    ORDER_BOOK_UPDATE = "order_book_update"
    TRADE = "trade"
    
    # 新闻/情报事件
    NEWS = "news"
    TWEET = "tweet"
    REGULATORY = "regulatory"
    FUNDAMENTAL = "fundamental"
    TECHNICAL = "technical"
    
    # 链上事件
    ONCHAIN_TRANSFER = "onchain_transfer"
    ONCHAIN_WHALE = "onchain_whale"
    ONCHAIN_PROTOCOL = "onchain_protocol"
    
    # 预测市场
    PREDICTION_MARKET = "prediction_market"
    
    # 宏观事件
    MACRO_EVENT = "macro_event"
    ETF_FLOW = "etf_flow"
    
    # 情绪/叙事
    SENTIMENT_CHANGE = "sentiment_change"
    NARRATIVE_SHIFT = "narrative_shift"
    REGIME_CHANGE = "regime_change"
    
    # 其他
    UNKNOWN = "unknown"


class Sentiment(Enum):
    """情绪方向"""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


class Importance(Enum):
    """重要性级别"""
    CRITICAL = 1.0    # 需立即关注
    HIGH = 0.75        # 重要
    MEDIUM = 0.5       # 中等
    LOW = 0.25         # 一般


class Source(Enum):
    """数据源"""
    # 官方 API
    BINANCE = "binance"
    OKX = "okx"
    COINGECKO = "coingecko"
    
    # 新闻/媒体
    COINDESK = "coindesk"
    COINTELEGRAPH = "cointelegraph"
    THEBLOCK = "theblock"
    ODALY = "odaily"
    JINSE = "jinse"
    BABI8 = "babi8"
    
    # 社交媒体
    TWITTER = "twitter"
    REDDIT = "reddit"
    TELEGRAM = "telegram"
    
    # Skills
    CLAWHUB_ODAILY = "clawhub_odaily"
    CLAWHUB_PANEWS = "clawhub_panews"
    CLAWHUB_JIN10 = "clawhub_jin10"
    
    # 链上
    ETHEREUM = "ethereum"
    DEXRANK = "dexrank"
    GLASSNODE = "glassnode"
    
    # 预测市场
    POLYMARKET = "polymarket"
    
    # 宏观
    YAHOO = "yahoo"
    CME = "cme"
    
    # 未知
    UNKNOWN = "unknown"


@dataclass
class StandardEvent:
    """标准事件 - 所有数据源的统一输出格式（系统共享合约）
    
    这是系统的核心公共语言，所有 Adapter 都应该输出这个格式。
    
    事件流向：
    External Source → Adapter → StandardEvent → EventBus → Consumers
    """
    
    # === 必需字段 ===
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: str = Source.UNKNOWN.value
    event_type: str = EventType.UNKNOWN.value
    timestamp: int = field(default_factory=lambda: int(datetime.now().timestamp()))
    created_at: int = field(default_factory=lambda: int(datetime.now().timestamp()))
    
    # === 内容 ===
    title: str = ""
    summary: str = ""
    content: str = ""
    url: str = ""
    
    # === 重要性/情绪 ===
    importance: float = 0.5  # 0-1
    sentiment: str = Sentiment.UNKNOWN.value  # bullish/bearish/neutral
    
    # === 相关标的 ===
    symbols: List[str] = field(default_factory=list)  # ["BTC", "ETH"]
    assets: List[str] = field(default_factory=list)   # ["BTC", "ETH", "USD"]
    
    # === 标签/分类 ===
    tags: List[str] = field(default_factory=list)        # ["ETF", "BlackRock"]
    narratives: List[str] = field(default_factory=list)   # ["ETF叙事", "机构入场"]
    event_subtype: str = ""                               # 事件子类型
    
    # === 关联数据 ===
    metadata: Dict[str, Any] = field(default_factory=dict)  # 原始数据副本
    
    # === 置信度 ===
    confidence: float = 1.0  # 数据置信度 0-1
    quality_score: float = 0.5  # 质量评分 0-1
    
    # === 溯源 ===
    original_id: str = ""     # 原始数据 ID
    original_url: str = ""    # 原始链接
    original_data: Dict = field(default_factory=dict)  # 完整原始数据
    
    def to_dict(self) -> Dict:
        """转换为字典"""
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
        """从字典创建"""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    def is_high_priority(self) -> bool:
        """是否高优先级"""
        return self.importance >= 0.75 or self.confidence >= 0.9
    
    def is_bullish(self) -> bool:
        """是否看多"""
        return self.sentiment == Sentiment.BULLISH.value
    
    def is_bearish(self) -> bool:
        """是否看空"""
        return self.sentiment == Sentiment.BEARISH.value
    
    def get_age_seconds(self) -> int:
        """获取事件年龄（秒）"""
        return int(datetime.now().timestamp()) - self.timestamp
    
    def get_age_minutes(self) -> float:
        """获取事件年龄（分钟）"""
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
        """检查事件是否匹配"""
        # 事件类型
        if self.event_types:
            if event.event_type not in [e.value for e in self.event_types]:
                return False
        
        # 来源
        if self.sources:
            if event.source not in [s.value for s in self.sources]:
                return False
        
        # 标的
        if self.symbols:
            if not any(s.upper() in [sym.upper() for sym in event.symbols]):
                return False
        
        # 重要性
        if event.importance < self.min_importance:
            return False
        
        # 置信度
        if event.confidence < self.min_confidence:
            return False
        
        # 情绪
        if self.sentiment and event.sentiment != self.sentiment.value:
            return False
        
        # 年龄
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
    """创建新闻事件的便捷函数"""
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
    """创建推文事件的便捷函数"""
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
    action: str,  # buy/sell/transfer
    symbol: str,
    amount: float,
    value_usd: float,
    exchange: str = ""
) -> StandardEvent:
    """创建巨鲸事件的便捷函数"""
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
        source=Source.CLAWHUB_ODAILY.value,  # 修正源为 ClawHub Odaily
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
