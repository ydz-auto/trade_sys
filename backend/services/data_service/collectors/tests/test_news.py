"""
Tests for NewsCollector
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from collectors import (
    NewsCollector, NewsItem, Deduplicator, BlackSwanDetector
)


class TestDeduplicator:
    def test_is_duplicate_same_title(self):
        deduplicator = Deduplicator()

        result1 = deduplicator.is_duplicate("BTC暴涨突破10万美元")
        assert result1 is False

        result2 = deduplicator.is_duplicate("BTC暴涨突破10万美元")
        assert result2 is True

    def test_is_duplicate_similar_title(self):
        deduplicator = Deduplicator(similarity_threshold=0.8)

        deduplicator.is_duplicate("BTC价格突破10万美元")
        result = deduplicator.is_duplicate("BTC价格突破10万美金")

        assert result is True

    def test_is_duplicate_different_title(self):
        deduplicator = Deduplicator()

        deduplicator.is_duplicate("BTC暴涨突破10万美元")
        result = deduplicator.is_duplicate("ETH创新高突破5000美元")

        assert result is False

    def test_clear(self):
        deduplicator = Deduplicator()

        deduplicator.is_duplicate("BTC暴涨突破10万美元")
        deduplicator.clear()

        result = deduplicator.is_duplicate("BTC暴涨突破10万美元")
        assert result is False


class TestBlackSwanDetector:
    def test_detect_normal_event(self):
        detector = BlackSwanDetector()

        result = detector.detect(
            "BTC价格上涨2%，市场平稳",
            "比特币今日小幅上涨..."
        )

        assert result["is_black_swan"] is False
        assert result["urgency"] == "normal"

    def test_detect_black_swan_keywords(self):
        detector = BlackSwanDetector()

        result = detector.detect(
            "SEC起诉Binance，涉嫌违规",
            "美国证券交易委员会..."
        )

        assert len(result["keywords_found"]) > 0
        assert "SEC起诉" in result["keywords_found"]

    def test_detect_crash_keywords(self):
        detector = BlackSwanDetector()

        result = detector.detect(
            "BTC暴跌20%，市场崩盘",
            "比特币价格闪崩..."
        )

        assert result["black_swan_score"] > 0.3
        assert result["urgency"] in ["critical", "urgent"]

    def test_detect_breaking_news(self):
        detector = BlackSwanDetector()

        result = detector.detect(
            "Breaking: 重大利好来袭",
            "突发重大消息..."
        )

        assert result["urgency"] == "critical"


class TestNewsItem:
    def test_create_news_item(self):
        item = NewsItem(
            id="test_123",
            source="coindesk",
            title="BTC测试新闻",
            content="这是测试内容",
            url="https://coindesk.com/test",
            published=1704067200
        )

        assert item.id == "test_123"
        assert item.sentiment == "neutral"
        assert item.is_black_swan is False


class TestNewsCollector:
    def test_init(self):
        with patch("collectors.news_collector.get_datasource_config_manager") as mock_config:
            mock_config.return_value.get_news_feeds.return_value = {
                "coindesk": "https://coindesk.com/rss"
            }
            collector = NewsCollector()

            assert "coindesk" in collector.sources

    def test_detect_black_swan(self):
        with patch("collectors.news_collector.get_datasource_config_manager") as mock_config:
            mock_config.return_value.get_news_feeds.return_value = {}
            collector = NewsCollector()

            item = NewsItem(
                id="test_123",
                source="coindesk",
                title="SEC起诉Binance",
                content="SEC指控Binance违规",
                url="https://coindesk.com/test",
                published=1704067200
            )

            collector._detect_black_swan([item])

            assert item.is_black_swan is True
            assert item.event_type == "black_swan"

    def test_get_black_swan_news(self):
        with patch("collectors.news_collector.get_datasource_config_manager") as mock_config:
            mock_config.return_value.get_news_feeds.return_value = {}
            collector = NewsCollector()

            item1 = NewsItem(
                id="1", source="test", title="Normal",
                content="Normal news", url="", published=1
            )
            item2 = NewsItem(
                id="2", source="test", title="SEC起诉",
                content="SEC crash", url="", published=2
            )
            item2.is_black_swan = True
            item2.black_swan_score = 0.8

            collector.latest_news = [item1, item2]

            black_swan = collector.get_black_swan_news()
            assert len(black_swan) == 1
            assert black_swan[0]["id"] == "2"

    def test_get_news_by_sentiment(self):
        with patch("collectors.news_collector.get_datasource_config_manager") as mock_config:
            mock_config.return_value.get_news_feeds.return_value = {}
            collector = NewsCollector()

            item1 = NewsItem(
                id="1", source="test", title="Bullish",
                content="BTC上涨", url="", published=1
            )
            item1.sentiment = "bullish"

            item2 = NewsItem(
                id="2", source="test", title="Bearish",
                content="BTC下跌", url="", published=2
            )
            item2.sentiment = "bearish"

            collector.latest_news = [item1, item2]

            bullish = collector.get_news_by_sentiment("bullish")
            assert len(bullish) == 1
            assert bullish[0]["sentiment"] == "bullish"
