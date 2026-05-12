"""
Enhanced RSS Feed Collector - 增强版 RSS 采集器
支持熔断、降级、重试机制
"""
import asyncio
import hashlib
from typing import List, Dict, Optional, Any
from datetime import datetime
from dataclasses import dataclass

import httpx
import feedparser
from bs4 import BeautifulSoup

from infrastructure.logging import get_logger
from infrastructure.resilience import (
    CircuitBreaker,
    CircuitBreakerConfig,
    get_circuit_breaker,
    RetryPolicy,
    RetryConfig,
    FallbackChain,
    PrimaryFallback,
    StaticValueFallback,
    create_default_chain
)

logger = get_logger("collectors.news_feed")


@dataclass
class NewsArticle:
    """新闻文章"""
    id: str
    title: str
    content: str
    url: str
    source: str
    published_at: int
    author: Optional[str] = None
    summary: Optional[str] = None
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class RSSFeedSource:
    """RSS 源配置"""
    
    def __init__(
        self,
        name: str,
        url: str,
        enabled: bool = True,
        priority: int = 1,
        timeout: float = 10.0
    ):
        self.name = name
        self.url = url
        self.enabled = enabled
        self.priority = priority
        self.timeout = timeout
        self.circuit_breaker = get_circuit_breaker(
            f"rss_{name}",
            CircuitBreakerConfig(
                name=f"rss_{name}",
                failure_threshold=3,
                recovery_timeout=60.0
            )
        )
        self.retry_policy = RetryPolicy(RetryConfig(
            max_attempts=2,
            initial_delay=1.0
        ))


class RSSFeedCollector:
    """增强版 RSS 采集器"""
    
    def __init__(self):
        self.sources: Dict[str, RSSFeedSource] = {}
        self.deduplicator = Deduplicator()
        self._init_default_sources()
    
    def _init_default_sources(self):
        """初始化默认源"""
        default_sources = {
            "cointelegraph": "https://cointelegraph.com/rss",
            "cryptonews": "https://cryptonews.com/news/feed/",
            "decrypt": "https://decrypt.co/feed",
            "theblock": "https://www.theblock.co/rss.xml",
            "bitcoinist": "https://bitcoinist.com/feed/",
            "dailyhodl": "https://dailyhodl.com/feed/",
            "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
        }
        
        for name, url in default_sources.items():
            self.add_source(name, url)
    
    def add_source(
        self,
        name: str,
        url: str,
        enabled: bool = True,
        priority: int = 1
    ):
        """添加 RSS 源"""
        self.sources[name] = RSSFeedSource(name, url, enabled, priority)
        logger.info(f"Added RSS source: {name} - {url}")
    
    def remove_source(self, name: str):
        """移除 RSS 源"""
        if name in self.sources:
            del self.sources[name]
            logger.info(f"Removed RSS source: {name}")
    
    async def collect_all(self) -> List[NewsArticle]:
        """采集所有源"""
        all_articles = []
        tasks = []
        
        sorted_sources = sorted(
            self.sources.values(),
            key=lambda s: s.priority
        )
        
        for source in sorted_sources:
            if source.enabled:
                tasks.append(self._collect_source(source))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for source, result in zip(sorted_sources, results):
            if isinstance(result, Exception):
                logger.error(f"Failed to collect from {source.name}: {result}")
            else:
                all_articles.extend(result)
        
        deduplicated = self.deduplicator.deduplicate(all_articles)
        logger.info(f"Collected {len(deduplicated)} unique articles from {len(self.sources)} sources")
        
        return sorted(
            deduplicated,
            key=lambda a: a.published_at,
            reverse=True
        )
    
    async def _collect_source(self, source: RSSFeedSource) -> List[NewsArticle]:
        """采集单个源"""
        async def _fetch():
            return await self._fetch_feed(source)
        
        fallback_chain = create_default_chain(
            primary_name=source.name,
            static_value=[]
        )
        
        try:
            result = await source.circuit_breaker.execute(
                lambda: source.retry_policy.execute(_fetch)
            )
            return result
        except Exception as e:
            logger.warning(f"Source {source.name} failed, using fallback: {e}")
            return await fallback_chain.execute(_fetch)
    
    async def _fetch_feed(self, source: RSSFeedSource) -> List[NewsArticle]:
        """实际获取 RSS Feed"""
        articles = []
        
        async with httpx.AsyncClient(timeout=source.timeout) as client:
            response = await client.get(source.url)
            response.raise_for_status()
            
            feed = feedparser.parse(response.text)
            
            for entry in feed.entries[:15]:
                article = self._parse_entry(entry, source.name)
                if article:
                    articles.append(article)
        
        logger.info(f"Fetched {len(articles)} articles from {source.name}")
        return articles
    
    def _parse_entry(self, entry: Any, source_name: str) -> Optional[NewsArticle]:
        """解析 RSS 条目"""
        try:
            title = entry.get("title", "").strip()
            if not title:
                return None
            
            content = ""
            if "summary" in entry:
                content = BeautifulSoup(entry.summary, "html.parser").get_text()
            elif "description" in entry:
                content = BeautifulSoup(entry.description, "html.parser").get_text()
            
            url = entry.get("link", "")
            published_at = self._parse_published_date(entry)
            author = entry.get("author", "")
            
            tags = []
            if "tags" in entry:
                tags = [tag.get("term", "") for tag in entry.tags if tag.get("term")]
            
            article_id = self._generate_id(title, url, source_name)
            
            return NewsArticle(
                id=article_id,
                title=title,
                content=content[:500],
                url=url,
                source=source_name,
                published_at=published_at,
                author=author,
                summary=content[:200],
                tags=tags
            )
        except Exception as e:
            logger.warning(f"Failed to parse entry from {source_name}: {e}")
            return None
    
    def _parse_published_date(self, entry: Any) -> int:
        """解析发布日期"""
        try:
            if "published_parsed" in entry:
                dt = datetime(*entry.published_parsed[:6])
                return int(dt.timestamp())
            elif "updated_parsed" in entry:
                dt = datetime(*entry.updated_parsed[:6])
                return int(dt.timestamp())
        except Exception:
            pass
        
        return int(datetime.now().timestamp())
    
    def _generate_id(self, title: str, url: str, source: str) -> str:
        """生成文章 ID"""
        content = f"{title}:{url}:{source}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    def get_source_status(self) -> Dict[str, Dict]:
        """获取源状态"""
        status = {}
        for name, source in self.sources.items():
            status[name] = {
                "enabled": source.enabled,
                "priority": source.priority,
                "circuit": source.circuit_breaker.get_stats()
            }
        return status


class Deduplicator:
    """去重器"""
    
    def __init__(self, expire_hours: int = 24):
        self.expire_hours = expire_hours
        self.seen: Dict[str, float] = {}
    
    def deduplicate(self, articles: List[NewsArticle]) -> List[NewsArticle]:
        """去重"""
        unique = []
        now = datetime.now().timestamp()
        
        for article in articles:
            key = self._get_key(article)
            
            if key in self.seen:
                if now - self.seen[key] < self.expire_hours * 3600:
                    continue
            
            self.seen[key] = now
            unique.append(article)
        
        self._cleanup_old(now)
        return unique
    
    def _get_key(self, article: NewsArticle) -> str:
        """获取去重键"""
        title_normalized = article.title.lower().strip()
        return hashlib.md5(title_normalized.encode()).hexdigest()
    
    def _cleanup_old(self, now: float):
        """清理过期条目"""
        expired = [
            key for key, ts in self.seen.items()
            if now - ts > self.expire_hours * 3600
        ]
        for key in expired:
            del self.seen[key]
