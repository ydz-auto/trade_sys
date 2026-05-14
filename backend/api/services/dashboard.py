"""
Dashboard Service - Trading Dashboard Logic
"""
from datetime import datetime
from typing import List
from ..schemas import (
    DashboardResponse,
    PriceItem,
    FactorItem,
    RegimeState,
    RiskIndex,
    RiskComponent,
    Signal,
    PositionItem,
    WeightVersion,
    DataSourceStatus,
    TraderItem,
    SocialPost,
    NewsItem,
    MacroData,
    FearGreedData,
    EtfData,
)
from .storage import get_factors


def get_dashboard_data() -> DashboardResponse:
    """Get dashboard data"""
    factors_data = get_factors()
    
    prices: List[PriceItem] = [
        PriceItem(
            symbol="BTC/USDT",
            price=62345.78,
            change24h=2.4,
            volume_24h=28.5,
            exchange="Binance"
        ),
        PriceItem(
            symbol="ETH/USDT",
            price=3456.23,
            change24h=1.8,
            volume_24h=15.2,
            exchange="OKX"
        ),
        PriceItem(
            symbol="SOL/USDT",
            price=178.56,
            change24h=-0.5,
            volume_24h=5.8,
            exchange="Binance"
        )
    ]

    composite_score = 0.65

    regime = RegimeState(
        state="trending_up",
        confidence=0.72,
        trendStrength=0.68
    )

    risk = RiskIndex(
        total=32,
        level="medium",
        components=RiskComponent(
            volatility=0.45,
            flow=0.32,
            sentiment=0.55,
            macro=0.28
        )
    )

    signal = Signal(
        action="hold",
        confidence=0.65,
        riskLevel="low",
        reason="Neutral trend with stable volatility"
    )

    factors: List[FactorItem] = [
        FactorItem(**f) for f in factors_data.values()
    ]

    positions: List[PositionItem] = [
        PositionItem(
            symbol="BTC/USDT",
            side="long",
            size=0.125,
            entryPrice=61000,
            leverage=2,
            pnl=1682.23,
            stopLoss=60000,
            takeProfit=65000
        ),
        PositionItem(
            symbol="ETH/USDT",
            side="long",
            size=2.5,
            entryPrice=3400,
            leverage=3,
            pnl=-140.75,
            stopLoss=3250,
            takeProfit=3600
        )
    ]

    weight_versions: List[WeightVersion] = [
        WeightVersion(
            version="v1.2.3",
            timestamp="2024-01-15T10:30:00Z",
            weights={"trend": 0.3, "momentum": 0.25, "volatility": 0.2, "sentiment": 0.15, "flow": 0.1},
            author="system"
        ),
        WeightVersion(
            version="v1.2.2",
            timestamp="2024-01-14T15:20:00Z",
            weights={"trend": 0.25, "momentum": 0.3, "volatility": 0.2, "sentiment": 0.15, "flow": 0.1},
            author="user"
        )
    ]

    data_sources: List[DataSourceStatus] = [
        DataSourceStatus(
            name="Binance",
            status="online",
            lastUpdate=datetime.now().isoformat(),
            recordsCount=12456
        ),
        DataSourceStatus(
            name="CryptoNews",
            status="online",
            lastUpdate=datetime.now().isoformat(),
            recordsCount=8543
        )
    ]

    traders: List[TraderItem] = [
        TraderItem(
            id="trader_1",
            name="CryptoKing",
            platform="Binance",
            followers=15000,
            sentiment=0.75,
            recentPosition="long",
            symbol="BTC/USDT",
            winRate=0.68
        ),
        TraderItem(
            id="trader_2",
            name="BearHunter",
            platform="OKX",
            followers=8500,
            sentiment=-0.25,
            recentPosition="short",
            symbol="ETH/USDT",
            winRate=0.55
        )
    ]

    social_posts: List[SocialPost] = [
        SocialPost(
            id="post_1",
            platform="twitter",
            author="CryptoWatcher",
            content="BTC looking strong! Expecting a breakout soon 🚀",
            sentiment=0.75,
            likes=1245,
            time="2h ago",
            timestamp=datetime.now().isoformat(),
            symbols=["BTC", "ETH"]
        )
    ]

    news: List[NewsItem] = [
        NewsItem(
            id="news_1",
            title="BlackRock's Bitcoin ETF sees record inflows",
            content="The ETF has seen over $500M in inflows this week...",
            source="CoinDesk",
            sentiment="positive",
            sentiment_score=0.8,
            published=int(datetime.now().timestamp() - 3600),
            url="https://example.com/news/1"
        ),
        NewsItem(
            id="news_2",
            title="Fed hints at possible rate cut in March",
            content="Federal Reserve officials suggest a rate cut might be coming...",
            source="Bloomberg",
            sentiment="positive",
            sentiment_score=0.65,
            published=int(datetime.now().timestamp() - 7200),
            url="https://example.com/news/2"
        )
    ]

    macro = MacroData(
        gold={"price": 2028.5, "change": 0.8},
        usd_index={"value": 103.2, "change": -0.3},
        oil={"price": 78.45, "change": 1.2}
    )

    fear_greed = FearGreedData(
        value=55,
        classification="Neutral",
        timestamp=datetime.now().isoformat()
    )

    etf = EtfData(
        symbol="BTC ETF",
        net_flow=125000000,
        inflow=180000000,
        outflow=55000000,
        confidence=0.85
    )

    return DashboardResponse(
        prices=prices,
        compositeScore=composite_score,
        regime=regime,
        risk=risk,
        signal=signal,
        factors=factors,
        positions=positions,
        weightVersions=weight_versions,
        dataSources=data_sources,
        traders=traders,
        socialPosts=social_posts,
        news=news,
        macro=macro,
        fearGreed=fear_greed,
        etf=etf
    )
