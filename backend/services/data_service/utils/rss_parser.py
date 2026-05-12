"""
RSS Parser - 统一的 RSS/Atom Feed 解析器
所有使用 RSS 的采集器都可以共用
"""
import asyncio
import hashlib
from typing import List, Dict, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field

import feedparser
import httpx
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

logger = get_logger("utils.rss_parser")


@dataclass
class RSSArticle:
    """统一的 RSS 文章结构"""
    id: str
    title: str
    content: str
    url: str
    source: str
    published_at: int
    author: Optional[str] = None
    summary: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    raw: Optional[Dict] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "url": self.url,
            "source": self.source,
            "published_at": self.published_at,
            "author": self.author,
            "summary": self.summary,
            "tags": self.tags
        }


@dataclass
class RSSSource:
    """RSS 源配置"""
    name: str
    url: str
    enabled: bool = True
    priority: int = 1
    timeout: float = 10.0
    max_articles: int = 15


class RSSParser:
    """统一 RSS 解析器
    
    所有采集器共用的 RSS 解析能力
    """
    
    def __init__(
        self,
        default_timeout: float = 10.0,
        enable_circuit_breaker: bool = True
    ):
        self.default_timeout = default_timeout
        self.enable_circuit_breaker = enable_circuit_breaker
        self._article_cache: Dict[str, RSSArticle] = {}
        self._seen_hashes: set = set()
        self._max_cache = 1000
    
    def _generate_article_id(self, title: str, url: str, source: str) -> str:
        """生成文章唯一 ID"""
        content = f"{title}{url}{source}"
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    def _is_duplicate(self, article_id: str) -> bool:
        """检查是否重复"""
        return article_id in self._seen_hashes
    
    def _mark_seen(self, article_id: str):
        """标记为已见"""
        self._seen_hashes.add(article_id)
        if len(self._seen_hashes) > self._max_cache:
            self._seen_hashes = set(list(self._seen_hashes)[-self._max_cache:])
    
    def _parse_date(self, entry: Any) -> int:
        """解析发布日期"""
        try:
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                dt = datetime(*entry.published_parsed[:6])
                return int(dt.timestamp())
            elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                dt = datetime(*entry.updated_parsed[:6])
                return int(dt.timestamp())
        except Exception:
            pass
        return int(datetime.now().timestamp())
    
    def _extract_content(self, entry: Any) -> str:
        """提取文章内容"""
        content = ""
        
        # 尝试多种字段
        for field_name in ["summary", "description", "content"]:
            if hasattr(entry, field_name):
                val = getattr(entry, field_name)
                if val:
                    content = val
                    break
        
        # 清理 HTML
        if content:
            try:
                soup = BeautifulSoup(content, "html.parser")
                content = soup.get_text(separator="\n", strip=True)
            except Exception:
                pass
        
        return content
    
    def _extract_tags(self, entry: Any) -> List[str]:
        """提取标签"""
        tags = []
        if hasattr(entry, "tags"):
            for tag in entry.tags:
                if hasattr(tag, "term"):
                    tags.append(tag.term)
                elif isinstance(tag, dict) and "term" in tag:
                    tags.append(tag["term"])
        return tags
    
    def _extract_author(self, entry: Any) -> Optional[str]:
        """提取作者"""
        if hasattr(entry, "author"):
            return entry.author
        elif hasattr(entry, "author_detail") and hasattr(entry.author_detail, "name":
            return entry.author_detail.name
        return None
    
    def parse_entry(
        self,
        entry: Any,
        source_name: str
    ) -> Optional[RSSArticle]:
        """解析单个 RSS 条目"""
        try:
            title = getattr(entry, "title", "").strip()
            if not title:
                return None
            
            url = getattr(entry, "link", getattr(entry, "id", ""))
            if not url:
                return None
            
            article_id = self._generate_article_id(title, url, source_name)
            
            # 检查重复
            if self._is_duplicate(article_id):
                return None
            
            content = self._extract_content(entry)
            tags = self._extract_tags(entry)
            author = self._extract_author(entry)
            published_at = self._parse_date(entry)
            
            article = RSSArticle(
                id=article_id,
                title=title,
                content=content[:5000],
                url=url,
                source=source_name,
                published_at=published_at,
                author=author,
                summary=content[:200] if content else None,
                tags=tags,
                raw=dict(entry) if hasattr(entry, "__dict__") else {}
            )
            
            self._mark_seen(article_id)
            return article
            
        except Exception as e:
            logger.warning(f"Failed to parse RSS entry: {e}")
            return None
    
    def parse_feed(
        self,
        feed_content: str,
        source_name: str,
        max_articles: int = 15
    ) -> List[RSSArticle]:
        """解析完整 RSS Feed"""
        articles = []
        
        try:
            feed = feedparser.parse(feed_content)
            
            if hasattr(feed, "entries"):
                for entry in feed.entries[:max_articles]:
                    article = self.parse_entry(entry, source_name)
                    if article:
                        articles.append(article)
        except Exception as e:
            logger.error(f"Failed to parse feed: {e}")
        
        return articles


class RSSFetcher:
    """RSS 抓取器（带弹性能力）
    
    带熔断、重试、降级的 RSS 抓取
    """
    
    def __init__(self):
        self.parser = RSSParser()
    
    async def fetch_feed(
        self,
        source: RSSSource
    ) -> List[RSSArticle]:
        """抓取单个 RSS Feed"""
        circuit_breaker = get_circuit_breaker(
            f"rss_{source.name}",
            CircuitBreakerConfig(
                name=f"rss_{source.name}",
                failure_threshold=3,
                recovery_timeout=60.0
            )
        )
        
        retry_policy = RetryPolicy(RetryConfig(
            max_attempts=2,
            initial_delay=1.0
        ))
        
        async def _fetch():
            return await self._do_fetch(source)
        
        try:
            return await circuit_breaker.execute(
                lambda: retry_policy.execute(_fetch)
            )
        except Exception as e:
            logger.warning(f"Feed {source.name} failed: {e}")
            return []
    
    async def _do_fetch(self, source: RSSSource) -> List[RSSArticle]:
        articles = []
        
        async with httpx.AsyncClient(timeout=source.timeout) as client:
            response = await client.get(source.url)
            response.raise_for_status()
            
            feed_content = response.text
            
            articles = self.parser.parse_feed(
                feed_content,
                source.name,
                source.max_articles
            )
            
            logger.info(f"Fetched {len(articles)} from {source.name}")
        
        return articles
    
    async def fetch_multiple(
        self,
        sources: List[RSSSource]
    ) -> List[RSSArticle]:
        """批量抓取多个 RSS Feed"""
        all_articles = []
        tasks = []
        
        enabled_sources = [s for s in sources if s.enabled]
        sorted_sources = sorted(
            enabled_sources,
            key=lambda s: s.priority
        )
        
        for source in sorted_sources:
            tasks.append(self.fetch_feed(source))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for articles in results:
            if isinstance(articles):
                all_articles.extend(articles)
        
        # 按发布时间排序
        return sorted(
            all_articles,
            key=lambda a: a.published_at,
            reverse=True
        )


# 预设的加密货币 RSS 源
PRESET_RSS_SOURCES = [
    RSSSource(
        name="Cointelegraph",
        url="https://cointelegraph.com/rss",
        priority=1
    ),
    RSSSource(
        name="CryptoNews",
        url="https://cryptonews.com/news/feed/",
        priority=1
    ),
    RSSSource(
        name="Decrypt",
        url="https://decrypt.co/feed",
        priority=2
    ),
    RSSSource(
        name="TheBlock",
        url="https://www.theblock.co/rss.xml",
        priority=2
    ),
    RSSSource(
        name="Bitcoinist",
        url="https://bitcoinist.com/feed/",
        priority=3
    ),
    RSSSource(
        name="DailyHODL",
        url="https://dailyhodl.com/feed/",
        priority=3
    ),
]
