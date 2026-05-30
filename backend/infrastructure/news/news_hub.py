import asyncio
import hashlib
from typing import List, Dict, Optional, Any, Callable, Set
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from infrastructure.logging import get_logger
from infrastructure.utilities.resilience.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, get_circuit_breaker
from infrastructure.utilities.resilience.retry import RetryPolicy, RetryConfig
from infrastructure.utilities.resilience.fallback import FallbackChain, create_default_chain

from engines.adapters.data.collectors.news_feed_collector import RSSFeedCollector, NewsArticle
from engines.adapters.data.collectors.news_api_collector import NewsAPICollector
from engines.adapters.data.collectors.twitter_collector import TwitterCollector, TwitterPost, AlertPriority

logger = get_logger("infrastructure.news.news_hub")


class NewsSource(Enum):
    RSS = "rss"
    API = "api"
    WEBHOOK = "webhook"
    TWITTER = "twitter"
    SCRAPER = "scraper"


@dataclass
class AggregatedNews:
    id: str
    title: str
    content: str
    url: str
    source: str
    source_type: NewsSource
    published_at: int
    collected_at: int
    sentiment: Optional[str] = None
    sentiment_score: float = 0.5
    is_breaking: bool = False
    is_black_swan: bool = False
    related_symbols: List[str] = None
    tags: List[str] = None

    def __post_init__(self):
        if self.related_symbols is None:
            self.related_symbols = []
        if self.tags is None:
            self.tags = []


class NewsHub:

    def __init__(self):
        self.rss_collector = RSSFeedCollector()
        self.api_collector = NewsAPICollector()
        self.twitter_collector = TwitterCollector()

        self.aggregated_news: List[AggregatedNews] = []
        self.max_news_cache = 500
        self.seen_ids: Set[str] = set()
        self.callbacks: List[Callable] = []

        self.circuit_breaker = get_circuit_breaker(
            "news_hub",
            CircuitBreakerConfig(
                name="news_hub",
                failure_threshold=10,
                recovery_timeout=60.0
            )
        )

        self.webhook_handlers: Dict[str, Callable] = {}
        self._init_webhook_handlers()

    def _init_webhook_handlers(self):
        self.webhook_handlers["coindesk"] = self._handle_coindesk_webhook
        self.webhook_handlers["cointelegraph"] = self._handle_cointelegraph_webhook
        self.webhook_handlers["cryptopanic"] = self._handle_cryptopanic_webhook
        self.webhook_handlers["custom"] = self._handle_custom_webhook

    def register_callback(self, callback: Callable):
        self.callbacks.append(callback)

    async def collect_all(self, currencies: Optional[List[str]] = None) -> List[AggregatedNews]:
        all_news = []
        tasks = []

        tasks.append(self._collect_rss())
        tasks.append(self._collect_api(currencies))
        tasks.append(self._collect_twitter())

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, list):
                all_news.extend(result)

        all_news = sorted(all_news, key=lambda n: n.published_at, reverse=True)
        self.aggregated_news = all_news[:self.max_news_cache]

        for news in all_news:
            await self._notify_callbacks(news)

        logger.info(f"Collected total {len(all_news)} aggregated news")
        return all_news

    async def _collect_rss(self) -> List[AggregatedNews]:
        try:
            articles = await self.rss_collector.collect_all()
            return [self._article_to_aggregated(a) for a in articles]
        except Exception as e:
            logger.error(f"RSS collection failed: {e}")
            return []

    async def _collect_api(self, currencies: Optional[List[str]] = None) -> List[AggregatedNews]:
        try:
            articles = await self.api_collector.collect_all(currencies)
            return [self._article_to_aggregated(a) for a in articles]
        except Exception as e:
            logger.error(f"API collection failed: {e}")
            return []

    async def _collect_twitter(self) -> List[AggregatedNews]:
        try:
            posts = await self.twitter_collector.collect_all()
            return [self._post_to_aggregated(p) for p in posts]
        except Exception as e:
            logger.error(f"Twitter collection failed: {e}")
            return []

    def _article_to_aggregated(self, article: NewsArticle) -> AggregatedNews:
        aggregated_id = self._generate_id(article.title, article.url)

        if aggregated_id in self.seen_ids:
            return None

        self.seen_ids.add(aggregated_id)

        return AggregatedNews(
            id=aggregated_id,
            title=article.title,
            content=article.content,
            url=article.url,
            source=article.source,
            source_type=NewsSource.RSS,
            published_at=article.published_at,
            collected_at=int(datetime.now().timestamp()),
            tags=article.tags or [],
            related_symbols=self._extract_symbols(article.title + " " + article.content)
        )

    def _post_to_aggregated(self, post: TwitterPost) -> AggregatedNews:
        aggregated_id = f"twitter_{post.id}"

        if aggregated_id in self.seen_ids:
            return None

        self.seen_ids.add(aggregated_id)

        is_breaking = any(k in post.text.lower() for k in [
            "breaking", "urgent", "just in", "breaking news"
        ])

        return AggregatedNews(
            id=aggregated_id,
            title=f"@{post.author_display_name}: {post.text[:100]}...",
            content=post.text,
            url=post.url,
            source=f"Twitter @{post.author_username}",
            source_type=NewsSource.TWITTER,
            published_at=post.created_at,
            collected_at=int(datetime.now().timestamp()),
            is_breaking=is_breaking,
            tags=post.hashtags,
            related_symbols=self._extract_symbols(post.text)
        )

    def _extract_symbols(self, text: str) -> List[str]:
        symbols = []
        text_upper = text.upper()

        symbol_map = {
            "BTC": ["BTC", "BITCOIN", "比特币"],
            "ETH": ["ETH", "ETHEREUM", "以太坊"],
            "SOL": ["SOL", "SOLANA"],
            "XRP": ["XRP", "RIPPLE"],
            "DOGE": ["DOGE", "DOGECOIN", "狗狗币"],
            "BNB": ["BNB", "BINANCECOIN", "币安"],
            "ADA": ["ADA", "CARDANO"],
            "AVAX": ["AVAX", "AVALANCHE"],
            "DOT": ["DOT", "POLKADOT"],
            "MATIC": ["MATIC", "POLYGON"],
        }

        for symbol, keywords in symbol_map.items():
            if any(kw.upper() in text_upper for kw in keywords):
                symbols.append(symbol)

        return symbols[:5]

    def _generate_id(self, title: str, url: str) -> str:
        content = f"{title}:{url}"
        return hashlib.md5(content.encode()).hexdigest()

    async def _notify_callbacks(self, news: AggregatedNews):
        if not news:
            return

        for callback in self.callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(news))
                else:
                    callback(news)
            except Exception as e:
                logger.error(f"Callback error: {e}")

    async def handle_webhook(self, source: str, data: Dict) -> Optional[AggregatedNews]:
        handler = self.webhook_handlers.get(source.lower(), self.webhook_handlers["custom"])

        try:
            news = await handler(data)
            if news:
                self.aggregated_news.insert(0, news)
                await self._notify_callbacks(news)
                logger.info(f"Received news from webhook: {source}")
            return news
        except Exception as e:
            logger.error(f"Webhook handler error for {source}: {e}")
            return None

    async def _handle_coindesk_webhook(self, data: Dict) -> Optional[AggregatedNews]:
        title = data.get("headline", "")
        content = data.get("body", "")
        url = data.get("url", "")

        if not title:
            return None

        aggregated_id = self._generate_id(title, url)
        if aggregated_id in self.seen_ids:
            return None
        self.seen_ids.add(aggregated_id)

        return AggregatedNews(
            id=aggregated_id,
            title=title,
            content=content[:500],
            url=url,
            source="CoinDesk Webhook",
            source_type=NewsSource.WEBHOOK,
            published_at=int(datetime.now().timestamp()),
            collected_at=int(datetime.now().timestamp()),
            related_symbols=self._extract_symbols(title + " " + content)
        )

    async def _handle_cointelegraph_webhook(self, data: Dict) -> Optional[AggregatedNews]:
        title = data.get("title", "")
        content = data.get("content", "")
        url = data.get("link", "")

        if not title:
            return None

        aggregated_id = self._generate_id(title, url)
        if aggregated_id in self.seen_ids:
            return None
        self.seen_ids.add(aggregated_id)

        return AggregatedNews(
            id=aggregated_id,
            title=title,
            content=content[:500],
            url=url,
            source="CoinTelegraph Webhook",
            source_type=NewsSource.WEBHOOK,
            published_at=int(datetime.now().timestamp()),
            collected_at=int(datetime.now().timestamp()),
            related_symbols=self._extract_symbols(title + " " + content)
        )

    async def _handle_cryptopanic_webhook(self, data: Dict) -> Optional[AggregatedNews]:
        title = data.get("title", "")
        url = data.get("url", "")

        if not title:
            return None

        aggregated_id = self._generate_id(title, url)
        if aggregated_id in self.seen_ids:
            return None
        self.seen_ids.add(aggregated_id)

        return AggregatedNews(
            id=aggregated_id,
            title=title,
            content=data.get("text", title)[:500],
            url=url,
            source="CryptoPanic Webhook",
            source_type=NewsSource.WEBHOOK,
            published_at=int(datetime.now().timestamp()),
            collected_at=int(datetime.now().timestamp()),
            related_symbols=self._extract_symbols(title)
        )

    async def _handle_custom_webhook(self, data: Dict) -> Optional[AggregatedNews]:
        title = data.get("title", data.get("headline", ""))
        content = data.get("content", data.get("body", data.get("text", "")))
        url = data.get("url", data.get("link", ""))

        if not title:
            return None

        aggregated_id = self._generate_id(title, url)
        if aggregated_id in self.seen_ids:
            return None
        self.seen_ids.add(aggregated_id)

        return AggregatedNews(
            id=aggregated_id,
            title=title,
            content=content[:500],
            url=url,
            source=data.get("source", "Custom Webhook"),
            source_type=NewsSource.WEBHOOK,
            published_at=int(datetime.now().timestamp()),
            collected_at=int(datetime.now().timestamp()),
            related_symbols=self._extract_symbols(title + " " + content)
        )

    def get_latest_news(self, limit: int = 20, source_type: Optional[NewsSource] = None) -> List[AggregatedNews]:
        news = self.aggregated_news

        if source_type:
            news = [n for n in news if n.source_type == source_type]

        return news[:limit]

    def get_black_swan_news(self) -> List[AggregatedNews]:
        return [n for n in self.aggregated_news if n.is_black_swan]

    def get_news_by_symbol(self, symbol: str, limit: int = 20) -> List[AggregatedNews]:
        symbol_upper = symbol.upper()
        filtered = [
            n for n in self.aggregated_news
            if symbol_upper in n.related_symbols
        ]
        return filtered[:limit]

    def get_status(self) -> Dict:
        return {
            "total_news": len(self.aggregated_news),
            "rss": self.rss_collector.get_source_status(),
            "api": self.api_collector.get_status(),
            "twitter": self.twitter_collector.get_monitoring_status(),
            "hub_circuit": self.circuit_breaker.get_stats()
        }
