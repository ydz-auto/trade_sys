"""
增强版新闻采集器 - 支持 LLM 资源池 + 多级降级 + 弹性能力
"""

import asyncio
import re
import hashlib
import json
from typing import List, Dict, Optional, Any
from datetime import datetime
import feedparser
import httpx
from bs4 import BeautifulSoup

from infrastructure.logging import get_logger
from infrastructure.llm import get_llm_pool, LLMPoolManager
from .base_collector import BaseCollector, CollectorResult, CollectorStatus
from infrastructure.resilience import CircuitBreakerConfig, RetryConfig

logger = get_logger("collectors.news")


class NewsItem:
    def __init__(self, title: str, content: str = "", source: str = "", url: str = ""):
        self.id = hashlib.md5(title.encode()).hexdigest()[:8]
        self.title = title
        self.content = content
        self.source = source
        self.url = url
        self.published = int(datetime.now().timestamp())
        self.sentiment = "neutral"
        self.sentiment_score = 0.5
        self.sentiment_confidence = 0.3
        self.event_type = "normal"
        self.affected_symbols = []
        self.black_swan_score = 0.0
        self.llm_pool_used: Optional[str] = None
        self._fallback_to_keyword: bool = False

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "source": self.source,
            "url": self.url,
            "published": self.published,
            "sentiment": self.sentiment,
            "sentiment_score": self.sentiment_score,
            "event_type": self.event_type,
            "affected_symbols": self.affected_symbols,
            "llm_pool_used": self.llm_pool_used,
            "used_keyword_fallback": self._fallback_to_keyword
        }


class Deduplicator:
    """带时间窗口的去重器 - 24小时内的新闻不重复"""
    
    def __init__(self, expire_hours: int = 24):
        self.expire_hours = expire_hours
        self.seen: Dict[str, float] = {}  # title_hash -> timestamp
    
    def _clean_expired(self):
        """清理过期条目"""
        now = datetime.now().timestamp()
        expired_keys = [
            key for key, ts in self.seen.items()
            if now - ts > self.expire_hours * 3600
        ]
        for key in expired_keys:
            del self.seen[key]
    
    def is_duplicate(self, title: str) -> bool:
        """检查是否重复，自动清理过期"""
        self._clean_expired()
        
        title_lower = title.lower().strip()
        title_hash = hashlib.md5(title_lower.encode()).hexdigest()
        
        if title_hash in self.seen:
            # 更新时间戳，延长生命周期
            self.seen[title_hash] = datetime.now().timestamp()
            return True
        
        self.seen[title_hash] = datetime.now().timestamp()
        return False


class BlackSwanDetector:
    def detect(self, title: str, content: str = "") -> Dict:
        text = (title + " " + content).lower()
        black_swan_keywords = [
            "crash", "collapse", "bankruptcy", "fraud", "hack",
            "massive", "catastrophic", "devastating",
            "暴跌", "崩盘", "破产", "欺诈"
        ]
        score = sum(1 for kw in black_swan_keywords if kw in text) * 0.2
        return {"black_swan_score": min(score, 1.0)}


class NewsCollector(BaseCollector):
    """增强版新闻采集器 - 支持 LLM 资源池 + 多级降级 + 弹性能力"""

    def __init__(self, use_llm: bool = True):
        self.use_llm = use_llm
        self.latest_news: List[NewsItem] = []
        self.deduplicator = Deduplicator()
        self.black_swan_detector = BlackSwanDetector()
        self.sources = self._init_sources()
        self.llm_pool: Optional[LLMPoolManager] = None

        # 调用基类初始化，配置弹性能力
        super().__init__(
            name="NewsCollector",
            circuit_config=CircuitBreakerConfig(
                name="news_circuit",
                failure_threshold=3,
                recovery_timeout=60.0
            ),
            retry_config=RetryConfig(
                max_attempts=2,
                initial_delay=1.0
            ),
            fallback_value=[]  # 降级时返回空列表
        )

        if self.use_llm:
            try:
                self.llm_pool = get_llm_pool()
                logger.info("LLM Pool initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize LLM Pool: {e}, will use keyword mode only")
                self.use_llm = False

    def _init_sources(self) -> Dict[str, str]:
        return {
            "cointelegraph": "https://cointelegraph.com/rss",
            "cryptonews": "https://cryptonews.com/news/feed/",
            "decrypt": "https://decrypt.co/feed",
            "theblock": "https://www.theblock.co/rss.xml",
            "bitcoinist": "https://bitcoinist.com/feed/",
        }

    async def collect(self) -> CollectorResult:
        """采集所有来源的新闻（返回 CollectorResult）"""
        try:
            all_news = []

            for source_name, url in self.sources.items():
                try:
                    news = await self._fetch_rss(source_name, url)
                    all_news.extend(news)
                    logger.info(f"[{source_name}] Fetched {len(news)} news")
                except Exception as e:
                    logger.warning(f"[{source_name}] Error: {e}")

            deduplicated = self._deduplicate(all_news)
            logger.info(f"After dedup: {len(deduplicated)} news")

            analyzed = await self._analyze_sentiment(deduplicated)
            self._detect_black_swan(analyzed)

            self.latest_news = sorted(
                analyzed,
                key=lambda x: (x.published, x.black_swan_score),
                reverse=True
            )[:50]

            if self.llm_pool:
                stats = self.llm_pool.get_pool_stats()
                logger.info(f"LLM Pool stats: {json.dumps(stats, ensure_ascii=False)}")

            logger.info(f"Total collected: {len(self.latest_news)} news")

            return CollectorResult(
                success=True,
                data=self.latest_news,
                source="NewsCollector",
                confidence=0.9
            )
        except Exception as e:
            logger.error(f"News collection failed: {e}")
            return CollectorResult(
                success=False,
                error=str(e),
                source="NewsCollector"
            )

    async def _fetch_rss(self, source_name: str, url: str) -> List[NewsItem]:
        if "api" in source_name:
            return await self._fetch_api(source_name, url)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                feed = feedparser.parse(response.text)
                news_items = []
                for entry in feed.entries[:10]:
                    title = entry.get("title", "")
                    content = entry.get("summary", "")[:200]
                    link = entry.get("link", "")
                    if title:
                        item = NewsItem(
                            title=title.strip(),
                            content=BeautifulSoup(content, "html.parser").get_text(),
                            source=source_name,
                            url=link
                        )
                        news_items.append(item)
                return news_items
        except Exception as e:
            logger.error(f"[{source_name}] RSS fetch error: {e}")
            return []

    async def _fetch_api(self, source_name: str, url: str) -> List[NewsItem]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                news_items = []
                if "results" in data:
                    for item in data["results"][:10]:
                        title = item.get("title", "")
                        if title:
                            news_items.append(NewsItem(
                                title=title,
                                content=item.get("meta", {}).get("description", "")[:200],
                                source=source_name,
                                url=item.get("url", "")
                            ))
                return news_items
        except Exception as e:
            logger.error(f"[{source_name}] API fetch error: {e}")
            return []

    def _deduplicate(self, news: List[NewsItem]) -> List[NewsItem]:
        unique_news = []
        for item in news:
            if not self.deduplicator.is_duplicate(item.title):
                unique_news.append(item)
        return unique_news

    async def _analyze_sentiment(self, news: List[NewsItem]) -> List[NewsItem]:
        """使用 LLM 池分析情绪（带降级）"""
        if not self.use_llm or not self.llm_pool:
            logger.info("Using keyword-only sentiment analysis")
            return self._analyze_sentiment_keyword_only(news)

        try:
            for item in news:
                try:
                    result = await self.llm_pool.analyze_news_sentiment(item.title, item.content)
                    item.sentiment = result.get("sentiment", "neutral")
                    item.sentiment_score = result.get("sentiment_score", 0.5)
                    item.affected_symbols = result.get("affected_symbols", [])
                    item.black_swan_score = 1.0 if result.get("is_black_swan", False) else 0.0
                    item.llm_pool_used = result.get("_pool_used")
                    item._fallback_to_keyword = result.get("_fallback", False)
                except Exception as e:
                    logger.warning(f"LLM analysis failed, falling back: {e}")
                    self._analyze_single_keyword(item)
        except Exception as e:
            logger.error(f"LLM batch failed: {e}, falling back to keyword only")
            return self._analyze_sentiment_keyword_only(news)

        return news

    def _analyze_sentiment_keyword_only(self, news: List[NewsItem]) -> List[NewsItem]:
        """纯关键词情绪分析（终极降级）"""
        for item in news:
            self._analyze_single_keyword(item)
        return news

    def _analyze_single_keyword(self, item: NewsItem):
        """单条关键词分析"""
        SENTIMENT_KEYWORDS = {
            "bullish": ["surge", "rally", "soar", "jump", "gain", "rise", "high", "breakout",
                       "bull", "bullish", "buy", "ETF", "approval", "positive", "上涨", "暴涨", "突破", "利好"],
            "bearish": ["crash", "plunge", "dump", "drop", "fall", "decline", "low",
                       "bear", "bearish", "sell", "hack", "ban", "negative", "下跌", "暴跌", "跌破", "利空"]
        }

        text = (item.title + " " + item.content).lower()
        bullish_count = sum(1 for kw in SENTIMENT_KEYWORDS["bullish"] if kw.lower() in text)
        bearish_count = sum(1 for kw in SENTIMENT_KEYWORDS["bearish"] if kw.lower() in text)

        total = bullish_count + bearish_count
        if total > 0:
            item.sentiment_score = bullish_count / total
            item.sentiment = "bullish" if bullish_count > bearish_count else "bearish"
        item._fallback_to_keyword = True

        symbols = self._extract_symbols(item.title)
        if symbols:
            item.affected_symbols = symbols

    def _extract_symbols(self, text: str) -> List[str]:
        symbols = []
        text_upper = text.upper()
        crypto_map = {
            "BTC": ["BTC", "BITCOIN", "比特币"],
            "ETH": ["ETH", "ETHEREUM", "以太坊"],
            "SOL": ["SOL", "SOLANA"],
            "XRP": ["XRP", "RIPPLE"],
            "DOGE": ["DOGE", "DOGECOIN", "狗狗币"],
            "BNB": ["BNB", "BINANCE"],
        }
        for symbol, keywords in crypto_map.items():
            if any(kw.upper() in text_upper for kw in keywords):
                symbols.append(symbol)
        return symbols[:3]

    def _detect_black_swan(self, news: List[NewsItem]):
        for item in news:
            if item.black_swan_score <= 0:
                detection = self.black_swan_detector.detect(item.title, item.content)
                item.black_swan_score = detection["black_swan_score"]

    def get_latest_news(self, limit: int = 20) -> List[Dict]:
        """获取最新新闻"""
        return [item.to_dict() for item in self.latest_news[:limit]]

    def get_black_swan_news(self, min_score: float = 0.5) -> List[Dict]:
        """获取黑天鹅新闻"""
        return [
            item.to_dict() for item in self.latest_news
            if item.black_swan_score >= min_score
        ]

    def get_news_by_sentiment(self, sentiment: str) -> List[Dict]:
        """按情绪获取新闻"""
        return [
            item.to_dict() for item in self.latest_news
            if item.sentiment == sentiment
        ]

    def get_news_by_symbol(self, symbol: str) -> List[Dict]:
        """按币种获取新闻"""
        return [
            item.to_dict() for item in self.latest_news
            if symbol.upper() in item.affected_symbols
        ]

    def get_item_count(self) -> int:
        """获取新闻数量"""
        return len(self.latest_news)
