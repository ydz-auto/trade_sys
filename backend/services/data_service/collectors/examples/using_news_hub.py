"""
Example: Using the NewsHub
This file shows how to use the new NewsHub system
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from infrastructure.logging import get_logger
from services.data_service.collectors import (
    NewsHub,
    NewsArticle,
    TwitterPost,
    AggregatedNews
)

logger = get_logger("example.news_hub")


async def main():
    # Create the news hub
    logger.info("Initializing NewsHub...")
    hub = NewsHub()
    
    # Optional: Add a custom account to twitter
    hub.twitter_collector.add_account(
        username="elonsmusk",
        display_name="Elon Musk",
        priority=1
    )
    
    # Add a custom alert rule
    hub.twitter_collector.add_alert_rule(
        id="btc_news",
        name="BTC Price News",
        keywords=["bitcoin", "btc", "surge", "rally"],
        exclude_keywords=["shib", "doge"],
        priority="high"
    )
    
    # Register callback for new news
    def on_news_received(news: AggregatedNews):
        print(f"\n{'='*60}")
        print(f"New News Received: {news.title[:80]}{'...' if len(news.title) > 80 else ''}")
        print(f"Source: {news.source} ({news.source_type.value}")
        print(f"Symbols: {', '.join(news.related_symbols)}")
        print(f"URL: {news.url}")
    
    hub.register_callback(on_news_received)
    
    # Collect from all sources
    logger.info("Collecting news from all sources...")
    all_news = await hub.collect_all(currencies=["BTC", "ETH", "SOL"])
    
    print(f"\n{'='*60}")
    print(f"Total news collected: {len(all_news)}")
    
    # Get latest news
    latest_news = hub.get_latest_news(limit=10)
    print(f"\nLatest 10 news:")
    for i, news in enumerate(latest_news, 1):
        print(f"{i}. [{news.source_type.value}] {news.title[:60]}...")
    
    # Get by symbol
    btc_news = hub.get_news_by_symbol("BTC", limit=5)
    print(f"\nBTC-related news: {len(btc_news)}")
    
    # Get status
    print(f"\nHub Status:")
    status = hub.get_status()
    print(f"  Total news: {status['total_news']}")
    print(f"  RSS sources: {len(status['rss'])}")
    print(f"  Circuit status: {status['hub_circuit']}")
    
    # Simulate webhook
    print(f"\n{'='*60}")
    print("Testing webhook handling...")
    webhook_data = {
        "title": "Breaking: Bitcoin ETF sees record inflows",
        "content": "BlackRock's IBIT Bitcoin ETF has seen record inflows today...",
        "url": "https://example.com/news/bitcoin-etf-record",
        "source": "Custom Source"
    }
    await hub.handle_webhook("custom", webhook_data)


if __name__ == "__main__":
    asyncio.run(main())
