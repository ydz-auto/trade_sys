"""
REST API News Collector - REST API 新闻采集器
支持 CryptoPanic, CoinGecko 等 API 源
"""
import asyncio
import hashlib
import os
from typing import List, Dict, Optional, Any
from datetime import datetime
from dataclasses import dataclass

import httpx

from infrastructure.logging import get_logger
from infrastructure.utilities.resilience.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, get_circuit_breaker
from infrastructure.utilities.resilience.retry import RetryPolicy, RetryConfig
from infrastructure.utilities.resilience.fallback import FallbackChain, create_default_chain
from .news_feed_collector import NewsArticle

logger = get_logger("collectors.news_api")


@dataclass
class APISourceConfig:
    """API 源配置"""
    name: str
    base_url: str
    enabled: bool = True
    priority: int = 1
    timeout: float = 15.0
    api_key_env: Optional[str] = None
    api_key: Optional[str] = None


class CryptoPanicCollector:
    """CryptoPanic 采集器"""
    
    BASE_URL = "https://cryptopanic.com/api/v1"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("CRYPTOPANIC_API_KEY", "public")
        self.circuit_breaker = get_circuit_breaker(
            "cryptopanic",
            CircuitBreakerConfig(
                name="cryptopanic",
                failure_threshold=3,
                recovery_timeout=60.0
            )
        )
        self.retry_policy = RetryPolicy(RetryConfig(
            max_attempts=2,
            initial_delay=2.0
        ))
        self.last_ids: set = set()
    
    async def fetch_news(self, currencies: Optional[List[str]] = None) -> List[NewsArticle]:
        """获取新闻"""
        async def _fetch():
            return await self._fetch_impl(currencies)
        
        fallback_chain = create_default_chain(
            primary_name="cryptopanic",
            static_value=[]
        )
        
        try:
            result = await self.circuit_breaker.execute(
                lambda: self.retry_policy.execute(_fetch)
            )
            return result
        except Exception as e:
            logger.warning(f"CryptoPanic failed, using fallback: {e}")
            return await fallback_chain.execute(_fetch)
    
    async def _fetch_impl(self, currencies: Optional[List[str]] = None) -> List[NewsArticle]:
        articles = []
        params = {"auth_token": self.api_key, "kind": "news"}
        
        if currencies:
            params["currencies"] = ",".join(currencies)
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(f"{self.BASE_URL}/posts/", params=params)
            response.raise_for_status()
            data = response.json()
            
            for post in data.get("results", []):
                article = self._parse_post(post)
                if article:
                    articles.append(article)
        
        logger.info(f"Fetched {len(articles)} articles from CryptoPanic")
        return articles
    
    def _parse_post(self, post: Dict) -> Optional[NewsArticle]:
        """解析帖子"""
        try:
            post_id = str(post.get("id", ""))
            if post_id in self.last_ids:
                return None
            
            if len(self.last_ids) > 1000:
                self.last_ids = set()
            self.last_ids.add(post_id)
            
            title = post.get("title", "").strip()
            if not title:
                return None
            
            url = post.get("url", "")
            source = post.get("source", {}).get("title", "cryptopanic")
            published_at = self._parse_date(post.get("created_at", ""))
            
            currencies = []
            for curr in post.get("currencies", []):
                if code := curr.get("code"):
                    currencies.append(code)
            
            article_id = self._generate_id(title, url)
            
            return NewsArticle(
                id=article_id,
                title=title,
                content=title,
                url=url,
                source=source,
                published_at=published_at,
                tags=currencies
            )
        except Exception as e:
            logger.warning(f"Failed to parse CryptoPanic post: {e}")
            return None
    
    def _parse_date(self, date_str: str) -> int:
        """解析日期"""
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return int(dt.timestamp())
        except Exception:
            return int(datetime.now().timestamp())
    
    def _generate_id(self, title: str, url: str) -> str:
        content = f"{title}:{url}"
        return hashlib.md5(content.encode()).hexdigest()[:12]


class CoinGeckoNewsCollector:
    """CoinGecko 新闻采集器"""
    
    BASE_URL = "https://www.coingecko.com"
    
    def __init__(self):
        self.circuit_breaker = get_circuit_breaker(
            "coingecko_news",
            CircuitBreakerConfig(
                name="coingecko_news",
                failure_threshold=3,
                recovery_timeout=60.0
            )
        )
        self.retry_policy = RetryPolicy(RetryConfig(
            max_attempts=2,
            initial_delay=2.0
        ))
        self.last_ids: set = set()
    
    async def fetch_news(self) -> List[NewsArticle]:
        """获取新闻"""
        async def _fetch():
            return await self._fetch_impl()
        
        fallback_chain = create_default_chain(
            primary_name="coingecko",
            static_value=[]
        )
        
        try:
            result = await self.circuit_breaker.execute(
                lambda: self.retry_policy.execute(_fetch)
            )
            return result
        except Exception as e:
            logger.warning(f"CoinGecko failed, using fallback: {e}")
            return await fallback_chain.execute(_fetch)
    
    async def _fetch_impl(self) -> List[NewsArticle]:
        articles = []
        
        try:
            from bs4 import BeautifulSoup
            
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(f"{self.BASE_URL}/en/news")
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, "html.parser")
                news_items = soup.select(".post")
                
                for item in news_items[:20]:
                    article = self._parse_item(item)
                    if article:
                        articles.append(article)
        except ImportError:
            logger.warning("BeautifulSoup not available, skipping CoinGecko")
        except Exception as e:
            logger.warning(f"Failed to fetch CoinGecko news: {e}")
        
        logger.info(f"Fetched {len(articles)} articles from CoinGecko")
        return articles
    
    def _parse_item(self, item) -> Optional[NewsArticle]:
        """解析新闻项"""
        try:
            title_elem = item.select_one(".title a")
            if not title_elem:
                return None
            
            title = title_elem.get_text(strip=True)
            if not title:
                return None
            
            article_id = hashlib.md5(title.encode()).hexdigest()[:12]
            if article_id in self.last_ids:
                return None
            
            if len(self.last_ids) > 1000:
                self.last_ids = set()
            self.last_ids.add(article_id)
            
            url = self.BASE_URL + title_elem.get("href", "")
            summary_elem = item.select_one(".post-excerpt")
            content = summary_elem.get_text(strip=True) if summary_elem else title
            
            return NewsArticle(
                id=article_id,
                title=title,
                content=content[:500],
                url=url,
                source="coingecko",
                published_at=int(datetime.now().timestamp()),
                summary=content[:200]
            )
        except Exception as e:
            logger.warning(f"Failed to parse CoinGecko item: {e}")
            return None


class NewsAPICollector:
    """综合 API 新闻采集器"""
    
    def __init__(self):
        self.cryptopanic = CryptoPanicCollector()
        self.coingecko = CoinGeckoNewsCollector()
    
    async def collect_all(self, currencies: Optional[List[str]] = None) -> List[NewsArticle]:
        """采集所有 API 源"""
        all_articles = []
        tasks = []
        
        tasks.append(self.cryptopanic.fetch_news(currencies))
        tasks.append(self.coingecko.fetch_news())
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, list):
                all_articles.extend(result)
        
        logger.info(f"Collected {len(all_articles)} articles from APIs")
        return all_articles
    
    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        return {
            "cryptopanic": self.cryptopanic.circuit_breaker.get_stats(),
            "coingecko": self.coingecko.circuit_breaker.get_stats()
        }
