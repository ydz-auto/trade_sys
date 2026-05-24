from typing import Any, Dict, Optional

import logging

logger = logging.getLogger(__name__)


async def collect_exchange_data(symbols: list = None) -> Dict[str, Any]:
    from engines.adapters.data.collectors import ExchangeCollector
    collector = ExchangeCollector()
    return await collector.collect(symbols)


async def collect_etf_data(symbols: list = None) -> Dict[str, Any]:
    from engines.adapters.data.collectors import ETFCollector
    collector = ETFCollector()
    return await collector.collect(symbols)


async def collect_news_data() -> Dict[str, Any]:
    from engines.adapters.data.collectors import NewsCollector
    collector = NewsCollector()
    return await collector.collect()


async def collect_macro_data() -> Dict[str, Any]:
    from engines.adapters.data.collectors import MacroCollector
    collector = MacroCollector()
    return await collector.collect()


async def collect_social_media_data() -> Dict[str, Any]:
    from engines.adapters.data.collectors import SocialMediaCollector
    collector = SocialMediaCollector()
    return await collector.collect()


async def collect_trader_data() -> Dict[str, Any]:
    from engines.adapters.data.collectors import TraderDataCollector
    collector = TraderDataCollector()
    return await collector.collect()


async def check_black_swan() -> Dict[str, Any]:
    from engines.adapters.data.collectors import NewsCollector
    collector = NewsCollector()
    await collector.collect()
    return collector.get_black_swan_news()


async def publish_exchange_prices(symbols: list = None, exchanges: list = None) -> Dict[str, Any]:
    from engines.adapters.data.collectors import ExchangeCollector
    collector = ExchangeCollector(
        symbols=symbols or ["BTC", "ETH", "SOL", "DOGE"],
        exchanges=exchanges or ["binance", "okx"],
    )
    return await collector.collect()


async def trigger_feature_generation(
    symbol: str,
    years: list = None,
    intervals: list = None,
    force_regenerate: bool = False,
) -> list:
    from application.commands.bus_commands import publish_command

    await publish_command(
        command_type="generate_features",
        data={
            "symbol": symbol,
            "years": years or [],
            "intervals": intervals or ["1m", "5m", "15m", "1h", "4h", "1d"],
            "force_regenerate": force_regenerate,
        },
        target="feature_runtime",
    )
    return []
