"""
Twitter Push Collector - Twitter 推送采集器

职责（业务逻辑）：
- 接收 Chrome Extension 转发的 Twitter 推送通知
- P0 账号过滤
- 币种关键词提取
- 事件标准化

运行时编排由 runtime/ingestion_runtime 负责
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional, Set, Callable
from dataclasses import dataclass, field

from shared.contracts import StandardEvent, Source, EventType, create_tweet_event
from infrastructure.logging import get_logger

logger = get_logger("collectors.twitter_push")

P0_ACCOUNTS = {
    "elonmusk", "cz_binance", "VitalikButerin", "saylor", "BarrySilbert",
    "binance", "okx", "coinbase", "EricBalchunas", "WatcherGuru", "Phyrex_Ni",
    "Saylor", "CZ_Binance", "VitalikButerin", "Phyrex_Ni"
}

CRYPTO_KEYWORDS = {
    "BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "DOT", "AVAX", "LINK",
    "MATIC", "UNI", "ATOM", "LTC", "BCH", "FIL", "NEAR", "APT", "ARB", "OP",
    "SUI", "SEI", "TIA", "INJ", "FTM", "ALGO", "XLM", "VET", "ICP",
    "SHIB", "PEPE", "WIF", "BONK", "SAND", "MANA"
}


@dataclass
class TwitterPushConfig:
    """Twitter Push 配置"""
    host: str = "localhost"
    port: int = 8765
    p0_accounts: Set[str] = field(default_factory=lambda: P0_ACCOUNTS)
    crypto_keywords: Set[str] = field(default_factory=lambda: CRYPTO_KEYWORDS)
    max_events: int = 1000


@dataclass
class TweetData:
    """推文数据"""
    id: str
    author: str
    content: str
    url: str = ""
    likes: int = 0
    retweets: int = 0
    hashtags: List[str] = field(default_factory=list)
    mentioned_symbols: List[str] = field(default_factory=list)


class TwitterPushCollector:
    """Twitter Push 采集器
    
    业务逻辑：
    - P0 账号过滤
    - 币种关键词提取
    - 事件标准化
    
    运行时编排（WebSocket 服务器）由 ingestion_runtime 负责
    """
    
    def __init__(self, config: TwitterPushConfig = None):
        self.config = config or TwitterPushConfig()
        
        self.events: List[StandardEvent] = []
        self.callbacks: List[Callable] = []
        
        self.stats = {
            "total_received": 0,
            "total_forwarded": 0,
            "p0_filtered": 0,
            "crypto_related": 0,
            "errors": 0
        }
    
    def process_tweet(self, tweet_data: Dict) -> Optional[StandardEvent]:
        """处理推文数据（业务逻辑）"""
        self.stats["total_received"] += 1
        
        try:
            author = tweet_data.get("author", "")
            content = tweet_data.get("content", "")
            
            is_p0 = any(acc.lower() in author.lower() for acc in self.config.p0_accounts)
            
            if not is_p0:
                self.stats["p0_filtered"] += 1
                logger.debug(f"P0 filtered: {author}")
                return None
            
            mentioned_symbols = tweet_data.get("mentionedSymbols", []) or []
            
            if not mentioned_symbols:
                mentioned_symbols = self._extract_crypto_symbols(content)
            
            if not mentioned_symbols and not self._is_crypto_related(content):
                logger.debug(f"Not crypto related: {content[:50]}...")
                return None
            
            self.stats["crypto_related"] += 1
            
            event = create_tweet_event(
                author=author,
                content=content,
                likes=tweet_data.get("likes", 0),
                retweets=tweet_data.get("retweets", 0),
                symbols=mentioned_symbols
            )
            
            event.source = Source.TWITTER.value
            event.event_type = EventType.TWEET.value
            
            event.metadata.update({
                "url": tweet_data.get("url", ""),
                "tweet_id": tweet_data.get("id", ""),
                "hashtags": tweet_data.get("hashtags", []),
                "is_p0_account": True,
                "push_source": "chrome_extension"
            })
            
            likes = tweet_data.get("likes", 0)
            retweets = tweet_data.get("retweets", 0)
            event.importance = self._calculate_importance(likes, retweets, mentioned_symbols)
            
            self.events.append(event)
            if len(self.events) > self.config.max_events:
                self.events = self.events[-self.config.max_events:]
            
            self.stats["total_forwarded"] += 1
            
            logger.info(f"Tweet processed: [{author}] {content[:50]}... (symbols: {mentioned_symbols})")
            
            self._notify_callbacks(event)
            
            return event
            
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Error processing tweet: {e}")
            return None
    
    def _extract_crypto_symbols(self, text: str) -> List[str]:
        """从文本中提取币种符号"""
        symbols = []
        text_upper = text.upper()
        
        for keyword in self.config.crypto_keywords:
            if keyword in text_upper:
                symbols.append(keyword)
        
        return symbols[:10]
    
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
        
        if likes > 10000 or retweets > 2000:
            base = 0.8
        elif likes > 1000 or retweets > 200:
            base = 0.65
        
        if len(symbols) >= 3:
            base = min(base + 0.1, 0.95)
        
        return min(base, 1.0)
    
    def register_callback(self, callback: Callable):
        """注册回调"""
        self.callbacks.append(callback)
    
    def _notify_callbacks(self, event: StandardEvent):
        """通知回调"""
        for callback in self.callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(event))
                else:
                    callback(event)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            **self.stats,
            "events_in_memory": len(self.events)
        }
    
    def get_recent_events(self, limit: int = 50) -> List[Dict]:
        """获取最近的事件"""
        events = self.events[-limit:]
        return [e.to_dict() for e in events]


_twitter_push_collector: Optional[TwitterPushCollector] = None


def get_twitter_push_collector(config: TwitterPushConfig = None) -> TwitterPushCollector:
    """获取 Twitter Push Collector 单例"""
    global _twitter_push_collector
    if _twitter_push_collector is None:
        _twitter_push_collector = TwitterPushCollector(config)
    return _twitter_push_collector
