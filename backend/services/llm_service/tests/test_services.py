"""
Tests for LLM Service
"""

import pytest
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestSentimentAnalyzer:
    def test_sentiment_prompt_structure(self):
        from services.llm_service.services.sentiment_analyzer import SentimentAnalyzer

        analyzer = SentimentAnalyzer()

        prompt = analyzer.SENTIMENT_PROMPT.format(text="BTC暴涨")
        assert "BTC暴涨" in prompt
        assert "JSON" in prompt


class TestNewsExtractor:
    def test_news_analysis_prompt(self):
        from services.llm_service.services.news_extractor import NewsExtractor

        extractor = NewsExtractor()

        prompt = extractor.NEWS_ANALYSIS_PROMPT.format(
            title="SEC批准BTC ETF",
            content="重大利好..."
        )

        assert "SEC批准BTC ETF" in prompt
        assert "JSON" in prompt


class TestSocialAnalyzer:
    def test_trader_analysis_prompt(self):
        from services.llm_service.services.social_analyzer import SocialAnalyzer

        analyzer = SocialAnalyzer()

        prompt = analyzer.TRADER_ANALYSIS_PROMPT.format(
            trader_name="CZ",
            platform="twitter",
            content="BTC looking strong!"
        )

        assert "CZ" in prompt
        assert "twitter" in prompt
        assert "BTC looking strong!" in prompt
