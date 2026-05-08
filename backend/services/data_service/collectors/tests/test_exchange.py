"""
Tests for ExchangeCollector
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from collectors import ExchangeCollector, ExchangePrice, MultiExchangePrices


class TestExchangePrice:
    def test_create_exchange_price(self):
        from datetime import datetime
        price = ExchangePrice(
            exchange="binance",
            symbol="BTC",
            price=95000.0,
            bid=94990.0,
            ask=95010.0,
            spread=20.0,
            spread_percent=0.02,
            volume_24h=25000.0,
            high_24h=96000.0,
            low_24h=94000.0,
            change_24h=2500.0,
            timestamp=datetime.now(),
            latency_ms=50,
            status="ok"
        )

        assert price.exchange == "binance"
        assert price.symbol == "BTC"
        assert price.price == 95000.0
        assert price.status == "ok"


class TestMultiExchangePrices:
    def test_available_exchanges(self):
        from datetime import datetime
        prices = MultiExchangePrices(symbol="BTC")
        prices.prices["binance"] = ExchangePrice(
            exchange="binance", symbol="BTC", price=95000.0,
            bid=94990.0, ask=95010.0, spread=20.0, spread_percent=0.02,
            volume_24h=25000.0, high_24h=96000.0, low_24h=94000.0,
            change_24h=2500.0, timestamp=datetime.now(), latency_ms=50
        )
        prices.prices["okx"] = ExchangePrice(
            exchange="okx", symbol="BTC", price=95050.0,
            bid=95040.0, ask=95060.0, spread=20.0, spread_percent=0.02,
            volume_24h=15000.0, high_24h=96000.0, low_24h=94000.0,
            change_24h=2500.0, timestamp=datetime.now(), latency_ms=60
        )

        assert len(prices.available_exchanges) == 2
        assert "binance" in prices.available_exchanges

    def test_arbitrage_opportunity(self):
        from datetime import datetime
        prices = MultiExchangePrices(symbol="BTC")
        prices.prices["binance"] = ExchangePrice(
            exchange="binance", symbol="BTC", price=94000.0,
            bid=93990.0, ask=94010.0, spread=20.0, spread_percent=0.02,
            volume_24h=25000.0, high_24h=96000.0, low_24h=94000.0,
            change_24h=2500.0, timestamp=datetime.now(), latency_ms=50
        )
        prices.prices["okx"] = ExchangePrice(
            exchange="okx", symbol="BTC", price=96000.0,
            bid=95990.0, ask=96010.0, spread=20.0, spread_percent=0.02,
            volume_24h=15000.0, high_24h=96000.0, low_24h=94000.0,
            change_24h=2500.0, timestamp=datetime.now(), latency_ms=60
        )

        arb = prices.arbitrage_opportunity(threshold_percent=0.5)
        assert arb is not None
        assert arb["buy_exchange"] == "binance"
        assert arb["sell_exchange"] == "okx"

    def test_no_arbitrage_below_threshold(self):
        from datetime import datetime
        prices = MultiExchangePrices(symbol="BTC")
        prices.prices["binance"] = ExchangePrice(
            exchange="binance", symbol="BTC", price=95000.0,
            bid=94990.0, ask=95010.0, spread=20.0, spread_percent=0.02,
            volume_24h=25000.0, high_24h=96000.0, low_24h=94000.0,
            change_24h=2500.0, timestamp=datetime.now(), latency_ms=50
        )
        prices.prices["okx"] = ExchangePrice(
            exchange="okx", symbol="BTC", price=95050.0,
            bid=95040.0, ask=95060.0, spread=20.0, spread_percent=0.02,
            volume_24h=15000.0, high_24h=96000.0, low_24h=94000.0,
            change_24h=2500.0, timestamp=datetime.now(), latency_ms=60
        )

        arb = prices.arbitrage_opportunity(threshold_percent=0.5)
        assert arb is None


class TestExchangeCollector:
    def test_init_with_symbols(self):
        collector = ExchangeCollector(
            symbols=["BTC", "ETH"],
            exchanges=["binance", "okx"]
        )

        assert collector.symbols == ["BTC", "ETH"]
        assert collector.exchanges == ["binance", "okx"]

    def test_get_latest_prices_empty(self):
        collector = ExchangeCollector(symbols=["BTC"], exchanges=["binance"])
        result = collector.get_latest_prices("BTC")
        assert result is None

    @pytest.mark.asyncio
    async def test_check_arbitrage_no_data(self):
        collector = ExchangeCollector(symbols=["BTC"], exchanges=["binance"])
        arb = collector.check_arbitrage("BTC")
        assert arb is None
