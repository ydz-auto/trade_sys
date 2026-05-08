"""
Pytest configuration and fixtures
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


@pytest.fixture
def mock_llm_sentiment_response():
    return {
        "sentiment": "bullish",
        "confidence": 0.9,
        "score": 0.7,
        "event_type": "normal",
        "black_swan_score": 0.1,
        "urgency": "normal",
        "affected_markets": ["BTC"],
        "affected_symbols": ["BTC"]
    }


@pytest.fixture
def mock_llm_news_analysis():
    return {
        "sentiment": "bullish",
        "confidence": 0.85,
        "score": 0.6,
        "event_type": "regulatory",
        "black_swan_score": 0.3,
        "urgency": "urgent",
        "affected_markets": ["BTC", "ETH"],
        "affected_symbols": ["IBIT", "FBTC"]
    }


@pytest.fixture
def mock_trader_analysis():
    return {
        "观点": "BTC还将继续上涨，突破10万美元",
        "情绪": "bullish",
        "情绪置信度": 0.85,
        "资产": ["BTC"],
        "时间预期": "long",
        "论据": ["机构持续买入", "ETF净流入创纪录"]
    }


@pytest.fixture
def mock_exchange_ticker():
    return {
        "symbol": "BTC/USDT",
        "last": 95000.0,
        "bid": 94999.0,
        "ask": 95001.0,
        "baseVolume": 25000.5,
        "high": 96000.0,
        "low": 94000.0,
        "change": 2500.0,
        "timestamp": 1704067200000
    }


@pytest.fixture
def mock_etf_flow():
    return {
        "netFlow": 150000000,
        "inflow": 150000000,
        "outflow": 0,
        "aum": 52000000000
    }


@pytest.fixture
def mock_macro_data():
    return {
        "gold": {"price": 2020.50, "change_1d": 0.5},
        "oil": {"price": 78.30, "change_1d": -0.3},
        "dxy": {"price": 104.2, "change_1d": 0.1}
    }


@pytest.fixture
def mock_social_post():
    return {
        "id": "12345",
        "platform": "twitter",
        "author": "CZ",
        "author_handle": "@cz_binance",
        "content": "BTC looking strong!",
        "url": "https://twitter.com/cz_binance/status/123",
        "published": 1704067200,
        "likes": 5000,
        "retweets": 1000
    }
