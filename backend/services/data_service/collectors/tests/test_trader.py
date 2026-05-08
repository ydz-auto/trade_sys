"""
Tests for TraderDataCollector
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from collectors import (
    TraderDataCollector, TraderStatement, OnChainData
)


class TestTraderStatement:
    def test_create_trader_statement(self):
        statement = TraderStatement(
            trader_id="cz_binance",
            trader_name="CZ",
            platform="twitter",
            content="BTC looking strong!",
            url="https://twitter.com/cz_binance/status/123",
            published=1704067200,
            sentiment="bullish",
            sentiment_score=0.7,
            mentioned_assets=["BTC"]
        )

        assert statement.trader_id == "cz_binance"
        assert statement.sentiment == "bullish"
        assert "BTC" in statement.mentioned_assets


class TestOnChainData:
    def test_create_onchain_data(self):
        data = OnChainData(
            wallet_address="0x1234567890",
            label="Whale Wallet",
            net_flow=1000000000,
            balance=50000000000,
            last_active=1704067200,
            source="dune"
        )

        assert data.wallet_address == "0x1234567890"
        assert data.net_flow > 0
        assert data.source == "dune"


class TestTraderDataCollector:
    def test_load_kol_list(self):
        with patch("collectors.trader_collector.KOL_TRADER_LIST", {
            "whale_trackers": {
                "traders": [
                    {"id": "cz_binance", "name": "CZ", "platforms": {"twitter": "@cz_binance"}}
                ]
            }
        }):
            with patch("collectors.trader_collector.get_datasource_config_manager"):
                collector = TraderDataCollector()
                assert len(collector.kol_list) == 1

    def test_aggregate_sentiment_no_data(self):
        with patch("collectors.trader_collector.KOL_TRADER_LIST", {"whale_trackers": {"traders": []}}):
            with patch("collectors.trader_collector.get_datasource_config_manager"):
                collector = TraderDataCollector()
                sentiment = collector.get_aggregate_sentiment()

                assert sentiment["sentiment"] == "neutral"
                assert sentiment["count"] == 0

    def test_aggregate_sentiment_bullish(self):
        with patch("collectors.trader_collector.KOL_TRADER_LIST", {"whale_trackers": {"traders": []}}):
            with patch("collectors.trader_collector.get_datasource_config_manager"):
                collector = TraderDataCollector()

                collector.latest_statements = [
                    TraderStatement(
                        trader_id="1", trader_name="A", platform="twitter",
                        content="", url="", published=1,
                        sentiment="bullish", sentiment_score=0.8,
                        credibility=0.9, influence_score=0.8
                    ),
                    TraderStatement(
                        trader_id="2", trader_name="B", platform="twitter",
                        content="", url="", published=2,
                        sentiment="bullish", sentiment_score=0.7,
                        credibility=0.8, influence_score=0.7
                    )
                ]

                sentiment = collector.get_aggregate_sentiment()

                assert sentiment["sentiment"] == "bullish"
                assert sentiment["bullish_count"] == 2
                assert sentiment["count"] == 2

    def test_get_opinions_by_asset(self):
        with patch("collectors.trader_collector.KOL_TRADER_LIST", {"whale_trackers": {"traders": []}}):
            with patch("collectors.trader_collector.get_datasource_config_manager"):
                collector = TraderDataCollector()

                collector.latest_statements = [
                    TraderStatement(
                        trader_id="1", trader_name="A", platform="twitter",
                        content="BTC上涨", url="", published=1,
                        mentioned_assets=["BTC"]
                    ),
                    TraderStatement(
                        trader_id="2", trader_name="B", platform="twitter",
                        content="ETH上涨", url="", published=2,
                        mentioned_assets=["ETH"]
                    )
                ]

                btc_opinions = collector.get_opinions_by_asset("BTC")
                assert len(btc_opinions) == 1

                eth_opinions = collector.get_opinions_by_asset("ETH")
                assert len(eth_opinions) == 1

    def test_get_opinions_by_sentiment(self):
        with patch("collectors.trader_collector.KOL_TRADER_LIST", {"whale_trackers": {"traders": []}}):
            with patch("collectors.trader_collector.get_datasource_config_manager"):
                collector = TraderDataCollector()

                collector.latest_statements = [
                    TraderStatement(
                        trader_id="1", trader_name="A", platform="twitter",
                        content="", url="", published=1, sentiment="bullish"
                    ),
                    TraderStatement(
                        trader_id="2", trader_name="B", platform="twitter",
                        content="", url="", published=2, sentiment="bearish"
                    )
                ]

                bullish = collector.get_bullish_traders()
                bearish = collector.get_bearish_traders()

                assert len(bullish) == 1
                assert len(bearish) == 1
