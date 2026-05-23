from typing import Any, Dict, Optional

from domain.logging import get_logger

logger = get_logger(__name__)


async def collect_exchange_data(symbols: list = None) -> Dict[str, Any]:
    from services.data_service.collectors import ExchangeCollector
    collector = ExchangeCollector()
    return await collector.collect(symbols)


async def collect_etf_data(symbols: list = None) -> Dict[str, Any]:
    from services.data_service.collectors import ETFCollector
    collector = ETFCollector()
    return await collector.collect(symbols)


async def collect_news_data() -> Dict[str, Any]:
    from services.data_service.collectors import NewsCollector
    collector = NewsCollector()
    return await collector.collect()


async def collect_macro_data() -> Dict[str, Any]:
    from services.data_service.collectors import MacroCollector
    collector = MacroCollector()
    return await collector.collect()


async def collect_social_media_data() -> Dict[str, Any]:
    from services.data_service.collectors import SocialMediaCollector
    collector = SocialMediaCollector()
    return await collector.collect()


async def collect_trader_data() -> Dict[str, Any]:
    from services.data_service.collectors import TraderDataCollector
    collector = TraderDataCollector()
    return await collector.collect()


async def check_black_swan() -> Dict[str, Any]:
    from services.data_service.collectors import NewsCollector
    collector = NewsCollector()
    await collector.collect()
    return collector.get_black_swan_news()


async def publish_exchange_prices(symbols: list = None, exchanges: list = None) -> Dict[str, Any]:
    from services.data_service.collectors import ExchangeCollector
    collector = ExchangeCollector(
        symbols=symbols or ["BTC", "ETH", "SOL", "DOGE"],
        exchanges=exchanges or ["binance", "okx"],
    )
    return await collector.collect()
