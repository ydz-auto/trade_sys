"""
News Collector - 新闻资讯采集（增强版）
支持：多源采集 + LLM情绪分析 + 去重 + 黑天鹅检测
"""

import asyncio
import time
import hashlib
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
import httpx
import feedparser
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from shared.config import get_datasource_config_manager
from shared.llm_client import LLMServiceClient
from infrastructure.logging import get_logger

logger = get_logger("collectors.news")


@dataclass
class NewsItem:
    """新闻条目"""
    id: str
    source: str
    title: str
    content: str
    url: str
    published: int
    timestamp: datetime = field(default_factory=datetime.now)
    sentiment: str = "neutral"
    sentiment_score: float = 0.0
    sentiment_confidence: float = 0.0
    event_type: str = "normal"
    black_swan_score: float = 0.0
    urgency: str = "normal"
    affected_symbols: List[str] = field(default_factory=list)
    is_black_swan: bool = False


class Deduplicator:
    """新闻去重器（基于标题相似度）"""

    def __init__(self, similarity_threshold: float = 0.8):
        self.similarity_threshold = similarity_threshold
        self.seen_hashes: Set[str] = set()
        self.seen_titles: List[str] = []

    def is_duplicate(self, title: str) -> bool:
        title_hash = hashlib.md5(title.lower().encode()).hexdigest()
        if title_hash in self.seen_hashes:
            return True

        for seen_title in self.seen_titles[-100:]:
            if self._similarity(title, seen_title) > self.similarity_threshold:
                return True

        self.seen_hashes.add(title_hash)
        self.seen_titles.append(title)
        return False

    def _similarity(self, s1: str, s2: str) -> float:
        s1_words = set(s1.lower().split())
        s2_words = set(s2.lower().split())

        if not s1_words or not s2_words:
            return 0.0

        intersection = len(s1_words & s2_words)
        union = len(s1_words | s2_words)

        return intersection / union if union > 0 else 0.0

    def clear(self):
        self.seen_hashes.clear()
        self.seen_titles.clear()


class BlackSwanDetector:
    """黑天鹅事件检测器"""

    BLACK_SWAN_KEYWORDS = {
        "sec": ["SEC起诉", "SEC指控", "SEC罚款", "SEC批准", "SEC拒绝"],
        "ftx": ["FTX", "Alameda", "SBF"],
        "hack": ["黑客攻击", "被盗", "漏洞", "攻击"],
        "ban": ["禁止", "禁令", "限制", "监管收紧"],
        "crash": ["暴跌", "崩盘", "大规模抛售", "踩踏"],
        " Whale": ["巨鲸", "大户", "抛售"],
        "exchange": ["交易所", "暂停", "冻结", "跑路"],
        "macro": ["加息", "缩表", "金融危机", "银行危机"],
    }

    URGENCY_KEYWORDS = {
        "critical": ["紧急", "立即", "突发", "Breaking"],
        "urgent": ["警告", "注意", "风险", "危机"],
        "normal": [],
        "low": ["解读", "分析", "观察"]
    }

    def detect(self, title: str, content: str) -> Dict:
        text = (title + " " + content).lower()
        keywords_found = []
        urgency = "normal"

        for category, keywords in self.BLACK_SWAN_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in text:
                    keywords_found.append(keyword)

        for level, keywords in self.URGENCY_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in text:
                    urgency = level
                    break

        black_swan_score = len(keywords_found) * 0.15
        black_swan_score = min(black_swan_score, 1.0)

        is_black_swan = black_swan_score > 0.5 or urgency in ["critical", "urgent"]

        return {
            "keywords_found": keywords_found,
            "black_swan_score": black_swan_score,
            "urgency": urgency,
            "is_black_swan": is_black_swan
        }


class NewsSourceCollector:
    """单个新闻源采集器"""

    def __init__(self, name: str, source_type: str, config: Dict):
        self.name = name
        self.source_type = source_type
        self.config = config

    async def collect(self) -> List[NewsItem]:
        if self.source_type == "rss":
            return await self._collect_rss()
        elif self.source_type == "rest_api":
            return await self._collect_rest()
        elif self.source_type == "llm_scraper":
            return await self._collect_llm()
        return []

    async def _collect_rss(self) -> List[NewsItem]:
        url = self.config.get("url")
        if not url:
            return []

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)

                if response.status_code == 200:
                    feed = feedparser.parse(response.text)
                    news_items = []

                    for entry in feed.entries[:20]:
                        item = NewsItem(
                            id=f"{self.name}_{hash(entry.get('link', ''))}",
                            source=self.name,
                            title=entry.get("title", ""),
                            content=entry.get("summary", "")[:1000] if entry.get("summary") else "",
                            url=entry.get("link", ""),
                            published=self._parse_timestamp(entry.get("published"))
                        )
                        news_items.append(item)

                    return news_items
        except Exception as e:
            logger.warning(f"RSS fetch error for {self.name}: {e}")
        return []

    async def _collect_rest(self) -> List[NewsItem]:
        url = self.config.get("url")
        if not url:
            return []

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)

                if response.status_code == 200:
                    data = response.json()
                    return self._parse_rest_response(data)
        except Exception as e:
            logger.warning(f"REST fetch error for {self.name}: {e}")
        return []

    async def _collect_llm(self) -> List[NewsItem]:
        url = self.config.get("scrape_url")
        if not url:
            return []

        try:
            from shared.http_client import HTTPClient, HTTPRequest, HTTPMethod
            http = HTTPClient()
            request = HTTPRequest(url=url, timeout=30.0)

            async with http:
                response = await http.request(request)

            if response.success and response.text:
                llm_client = LLMServiceClient()
                result = await llm_client.structured_extraction(
                    content=response.text,
                    prompt="从新闻页面中提取最新新闻列表，每条包含：title(标题)、content(摘要，100字内)、url(链接)"
                )

                if result and "news" in result:
                    news_items = []
                    for item in result["news"][:10]:
                        news_items.append(NewsItem(
                            id=f"{self.name}_{hash(item.get('url', ''))}",
                            source=self.name,
                            title=item.get("title", ""),
                            content=item.get("content", ""),
                            url=item.get("url", ""),
                            published=int(time.time())
                        ))
                    return news_items
        except Exception as e:
            logger.warning(f"LLM scraper error for {self.name}: {e}")
        return []

    def _parse_timestamp(self, date_str: Optional[str]) -> int:
        if not date_str:
            return int(time.time())
        try:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(date_str)
            return int(dt.timestamp())
        except Exception:
            return int(time.time())

    def _parse_rest_response(self, data: Dict) -> List[NewsItem]:
        return []


class NewsCollector:
    """新闻收集器（多源+去重+黑天鹅+情绪分析）"""

    def __init__(self):
        self.latest_news: List[NewsItem] = []
        self.sources: Dict[str, NewsSourceCollector] = {}
        self.deduplicator = Deduplicator()
        self.black_swan_detector = BlackSwanDetector()
        self.llm_client = LLMServiceClient()
        self._init_sources()

    def _init_sources(self):
        ds_config = get_datasource_config_manager()
        rss_feeds = ds_config.get_news_feeds()

        for source_name, url in rss_feeds.items():
            self.sources[source_name] = NewsSourceCollector(
                name=source_name,
                source_type="rss",
                config={"url": url}
            )

        rest_configs = [
            {"name": "cryptopanic", "url": "https://cryptopanic.com/api/v1/posts/"},
            {"name": "coinmetrics", "url": "https://api.coinmetrics.io/v4/"}
        ]

        for config in rest_configs:
            self.sources[config["name"]] = NewsSourceCollector(
                name=config["name"],
                source_type="rest_api",
                config={"url": config["url"]}
            )

        llm_configs = [
            {"name": "cointelegraph", "scrape_url": "https://cointelegraph.com/"},
            {"name": "jinshi", "scrape_url": "https://m.jin10.com/"}
        ]

        for config in llm_configs:
            self.sources[config["name"]] = NewsSourceCollector(
                name=config["name"],
                source_type="llm_scraper",
                config=config
            )

    async def collect(self) -> List[NewsItem]:
        all_news = []
        tasks = [collector.collect() for collector in self.sources.values()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"Source collection error: {result}")
            elif isinstance(result, list):
                all_news.extend(result)

        deduplicated = self._deduplicate(all_news)
        analyzed = await self._analyze_sentiment(deduplicated)
        self._detect_black_swan(analyzed)

        self.latest_news = sorted(
            analyzed,
            key=lambda x: (x.published, x.black_swan_score),
            reverse=True
        )[:50]

        return self.latest_news

    def _deduplicate(self, news: List[NewsItem]) -> List[NewsItem]:
        unique_news = []
        for item in news:
            if not self.deduplicator.is_duplicate(item.title):
                unique_news.append(item)
        return unique_news

    async def _analyze_sentiment(self, news: List[NewsItem]) -> List[NewsItem]:
        for item in news:
            try:
                result = await self.llm_client.news_analysis(item.title, item.content)

                item.sentiment = result.get("sentiment", "neutral")
                item.sentiment_score = result.get("score", 0.0)
                item.sentiment_confidence = result.get("confidence", 0.5)
                item.event_type = result.get("event_type", "normal")
                item.affected_symbols = result.get("affected_symbols", [])
            except Exception as e:
                logger.warning(f"Sentiment analysis error: {e}")

        return news

    def _detect_black_swan(self, news: List[NewsItem]):
        for item in news:
            detection = self.black_swan_detector.detect(item.title, item.content)
            item.black_swan_score = detection["black_swan_score"]
            item.urgency = detection["urgency"]
            item.is_black_swan = detection["is_black_swan"]

            if item.is_black_swan:
                item.event_type = "black_swan"

    def get_latest_news(self, limit: int = 20, include_black_swan: bool = True) -> List[Dict]:
        news = self.latest_news

        if not include_black_swan:
            news = [n for n in news if not n.is_black_swan]

        return [self._to_dict(item) for item in news[:limit]]

    def get_black_swan_news(self) -> List[Dict]:
        return [self._to_dict(n) for n in self.latest_news if n.is_black_swan]

    def get_news_by_sentiment(self, sentiment: str) -> List[Dict]:
        return [self._to_dict(n) for n in self.latest_news if n.sentiment == sentiment]

    def _to_dict(self, item: NewsItem) -> Dict:
        return {
            "id": item.id,
            "source": item.source,
            "title": item.title,
            "content": item.content,
            "url": item.url,
            "published": item.published,
            "timestamp": item.timestamp.isoformat(),
            "sentiment": item.sentiment,
            "sentiment_score": item.sentiment_score,
            "sentiment_confidence": item.sentiment_confidence,
            "event_type": item.event_type,
            "black_swan_score": item.black_swan_score,
            "urgency": item.urgency,
            "affected_symbols": item.affected_symbols,
            "is_black_swan": item.is_black_swan
        }
