"""
Data Service Collectors
"""

from .base_collector import (
    BaseCollector,
    MultiSourceCollector,
    CollectorResult,
    CollectorStatus,
    SourceConfig
)

from .multi_source import (
    MultiSourceCollector as BaseMultiSourceCollector,
    CrossValidator,
    DataFusion,
    FusionResult
)

from .llm_scraper import (
    LLMScraperBase,
    FireCrawlScraper,
    BeautifulSoupScraper,
    LLMStructuredExtractor,
    ScraperFactory,
    ScraperType,
    ScrapedContent
)

from .exchange_collector import (
    ExchangeCollector,
    ExchangeWebSocketCollector,
    ExchangePrice,
    MultiExchangePrices
)

from .etf_collector import (
    ETFCollector,
    ETFSourceCollector,
    ETFFlowData,
    ETFFlowResult
)

from .macro_collector import (
    MacroCollector,
    MacroSourceCollector,
    MacroData,
    MacroResult
)

try:
    from .news_collector import (
        NewsCollector,
        NewsSourceCollector,
        NewsItem,
        Deduplicator,
        BlackSwanDetector
    )
except ImportError:
    try:
        from .news_collector_simple import (
            NewsCollector,
            NewsItem,
            Deduplicator,
            BlackSwanDetector
        )
        NewsSourceCollector = NewsCollector
    except ImportError:
        NewsCollector = None
        NewsSourceCollector = None
        NewsItem = None
        Deduplicator = None
        BlackSwanDetector = None

from .social_media_collector import (
    SocialMediaCollector,
    TwitterCollector as LegacyTwitterCollector,
    RedditCollector,
    SocialPost
)

from .crypto_stock_collector import (
    CryptoStockCollector,
    YahooFinanceCollector,
    AlphaVantageCollector,
    CryptoStock
)

from .trader_collector import (
    TraderDataCollector,
    TwitterKOLCollector,
    DuneAnalyticsCollector,
    TraderStatement,
    OnChainData
)

# New Enhanced News Collection Modules
from .news_feed_collector import (
    RSSFeedCollector,
    NewsArticle,
    RSSFeedSource,
    Deduplicator as ArticleDeduplicator
)

from .news_api_collector import (
    NewsAPICollector,
    CryptoPanicCollector,
    CoinGeckoNewsCollector,
    APISourceConfig
)

from .twitter_collector import (
    TwitterCollector,
    TwitterPost,
    TwitterAccount,
    AlertRule,
    AlertPriority
)

from .news_hub import (
    NewsHub,
    AggregatedNews,
    NewsSource
)

__all__ = [
    "BaseCollector",
    "MultiSourceCollector",
    "CollectorResult",
    "CollectorStatus",
    "SourceConfig",
    "CrossValidator",
    "DataFusion",
    "FusionResult",
    "LLMScraperBase",
    "FireCrawlScraper",
    "BeautifulSoupScraper",
    "LLMStructuredExtractor",
    "ScraperFactory",
    "ScraperType",
    "ScrapedContent",
    "ExchangeCollector",
    "ExchangeWebSocketCollector",
    "ExchangePrice",
    "MultiExchangePrices",
    "ETFCollector",
    "ETFSourceCollector",
    "ETFFlowData",
    "ETFFlowResult",
    "MacroCollector",
    "MacroSourceCollector",
    "MacroData",
    "MacroResult",
    "NewsCollector",
    "NewsSourceCollector",
    "NewsItem",
    "Deduplicator",
    "BlackSwanDetector",
    "SocialMediaCollector",
    "LegacyTwitterCollector",
    "RedditCollector",
    "SocialPost",
    "CryptoStockCollector",
    "YahooFinanceCollector",
    "AlphaVantageCollector",
    "CryptoStock",
    "TraderDataCollector",
    "TwitterKOLCollector",
    "DuneAnalyticsCollector",
    "TraderStatement",
    "OnChainData",
    # New Enhanced Modules
    "RSSFeedCollector",
    "NewsArticle",
    "RSSFeedSource",
    "ArticleDeduplicator",
    "NewsAPICollector",
    "CryptoPanicCollector",
    "CoinGeckoNewsCollector",
    "APISourceConfig",
    "TwitterCollector",
    "TwitterPost",
    "TwitterAccount",
    "AlertRule",
    "AlertPriority",
    "NewsHub",
    "AggregatedNews",
    "NewsSource",
]
