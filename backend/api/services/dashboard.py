"""
Dashboard Service - Trading Dashboard Logic

从 Projection 读取真实状态
遵循"Data Service 统一采集 + 下游订阅"模式

Mock 模式控制:
  - 环境变量 DASHBOARD_MOCK=true 时返回模拟数据
  - 默认为 false，返回真实数据或空数据
"""

import os
from datetime import datetime
from typing import List, Dict, Any, Optional
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

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
from .projection_reader import get_projection_reader

from infrastructure.cache import get_redis_client


def _is_mock_mode() -> bool:
    """检查是否启用 mock 模式"""
    return os.getenv("DASHBOARD_MOCK", "false").lower() == "true"


async def get_dashboard_data() -> DashboardResponse:
    """Get dashboard data from Projection"""
    reader = await get_projection_reader()
    
    state = await reader.get_dashboard_state()
    
    prices = await _build_prices(state)
    factors = await _build_factors(state)
    regime = await _build_regime(state)
    risk = await _build_risk(reader)
    signal = await _build_signal(state)
    positions = await _build_positions(reader)
    news = await _build_news(state)
    
    return DashboardResponse(
        prices=prices,
        compositeScore=state.get("compositeScore", 0.5),
        regime=regime,
        risk=risk,
        signal=signal,
        factors=factors,
        positions=positions,
        weightVersions=await _get_weight_versions(),
        dataSources=await _get_data_sources(),
        traders=await _get_traders(),
        socialPosts=await _get_social_posts(),
        news=news,
        macro=await _get_macro(),
        fearGreed=await _get_fear_greed(),
        etf=await _get_etf(),
    )


async def _build_prices(state: Dict[str, Any]) -> List[PriceItem]:
    """构建价格列表"""
    prices_data = state.get("prices", {})
    
    if prices_data:
        return [
            PriceItem(
                symbol=data.get("symbol", symbol),
                price=data.get("price", 0),
                change24h=data.get("change24h", 0),
                volume_24h=data.get("volume_24h", 0),
                exchange=data.get("exchange", "binance"),
            )
            for symbol, data in prices_data.items()
        ]
    
    redis = None
    try:
        redis = get_redis_client()
    except Exception:
        pass
    
    if redis:
        try:
            import json
            real_prices = []
            symbols = ["BTC", "ETH", "SOL", "DOGE"]
            
            for symbol in symbols:
                for exchange in ["binance", "coingecko"]:
                    price_key = f"price:{symbol}:{exchange}"
                    price_data = await redis.get(price_key)
                    
                    if price_data:
                        if isinstance(price_data, str):
                            price_data = json.loads(price_data)
                        
                        real_prices.append(PriceItem(
                            symbol=f"{symbol}/USDT",
                            price=price_data.get("price", 0),
                            change24h=price_data.get("change_24h", 0) / 100 if price_data.get("change_24h") else 0,
                            volume_24h=price_data.get("volume_24h", 0) / 1e6 if price_data.get("volume_24h") else 0,
                            exchange=exchange.capitalize()
                        ))
                        break
            
            if real_prices:
                return real_prices
        except Exception:
            pass
    
    if _is_mock_mode():
        return _mock_prices()
    
    return []


async def _build_factors(state: Dict[str, Any]) -> List[FactorItem]:
    """构建因子列表"""
    factors_data = state.get("factors", {})
    
    if factors_data:
        result = []
        for name, f in factors_data.items():
            if isinstance(f, dict):
                result.append(FactorItem(
                    type=f.get("type", "unknown"),
                    name=f.get("name", name),
                    nameEn=f.get("nameEn", name),
                    weight=f.get("weight", 0.2),
                    value=f.get("value", 0.5),
                    confidence=f.get("confidence", 50),
                    color=f.get("color", "blue"),
                ))
            else:
                result.append(FactorItem(
                    type="factor",
                    name=name,
                    nameEn=name,
                    weight=0.2,
                    value=float(f) if isinstance(f, (int, float)) else 0.5,
                    confidence=50,
                    color="blue",
                ))
        return result
    
    factors_raw = get_factors()
    if factors_raw:
        return [FactorItem(**f) for f in factors_raw.values()]
    
    if _is_mock_mode():
        return _mock_factors()
    
    return []


async def _build_regime(state: Dict[str, Any]) -> RegimeState:
    """构建市场状态"""
    regime_data = state.get("regime", {}).get("BTC", {})
    
    if regime_data:
        return RegimeState(
            state=regime_data.get("state", "neutral"),
            confidence=regime_data.get("confidence", 0.5),
            trendStrength=regime_data.get("trendStrength", 0.5),
        )
    
    if _is_mock_mode():
        return RegimeState(
            state="trending_up",
            confidence=0.72,
            trendStrength=0.68
        )
    
    return RegimeState(
        state="unknown",
        confidence=0.0,
        trendStrength=0.0
    )


async def _build_risk(reader) -> RiskIndex:
    """构建风险指标"""
    risk_state = await reader.get_risk_state()
    
    if risk_state and risk_state.get("score") is not None:
        components = risk_state.get("components", {})
        return RiskIndex(
            total=risk_state.get("score", 0),
            level=risk_state.get("level", "unknown"),
            components=RiskComponent(
                volatility=components.get("volatility", 0.0),
                flow=components.get("flow", 0.0),
                sentiment=components.get("sentiment", 0.0),
                macro=components.get("macro", 0.0),
            )
        )
    
    if _is_mock_mode():
        return RiskIndex(
            total=35,
            level="low",
            components=RiskComponent(
                volatility=0.42,
                flow=0.28,
                sentiment=0.55,
                macro=0.15,
            )
        )
    
    return RiskIndex(
        total=0,
        level="unknown",
        components=RiskComponent(
            volatility=0.0,
            flow=0.0,
            sentiment=0.0,
            macro=0.0,
        )
    )


async def _build_signal(state: Dict[str, Any]) -> Signal:
    """构建信号"""
    signals = state.get("signals", {})
    
    if signals:
        btc_signal = signals.get("BTC/USDT") or signals.get("BTCUSDT") or signals.get("BTC")
        if btc_signal:
            direction = btc_signal.get("direction", "neutral")
            action = "long" if direction == "bullish" else "short" if direction == "bearish" else "hold"
            
            return Signal(
                action=action,
                confidence=btc_signal.get("confidence", 0.5),
                riskLevel="low",
                reason=f"Signal: {btc_signal.get('signal_name', 'Unknown')}",
            )
    
    if _is_mock_mode():
        return Signal(
            action="hold",
            confidence=0.65,
            riskLevel="low",
            reason="Neutral trend with stable volatility"
        )
    
    return Signal(
        action="hold",
        confidence=0.0,
        riskLevel="unknown",
        reason="No signal data available"
    )


async def _build_positions(reader) -> List[PositionItem]:
    """构建持仓列表"""
    positions_data = await reader.get_positions()
    
    if positions_data:
        return [
            PositionItem(
                symbol=symbol,
                side=data.get("side", "long"),
                size=abs(data.get("size", 0)),
                entryPrice=data.get("entry_price", 0),
                leverage=data.get("leverage", 1),
                pnl=data.get("unrealized_pnl", 0) + data.get("realized_pnl", 0),
                stopLoss=data.get("stop_loss"),
                takeProfit=data.get("take_profit"),
            )
            for symbol, data in positions_data.items()
            if data.get("size", 0) != 0
        ]
    
    redis = None
    try:
        redis = get_redis_client()
    except Exception:
        pass
    
    if redis:
        try:
            import json
            positions_key = "positions:active"
            positions = await redis.get(positions_key)
            
            if positions:
                if isinstance(positions, str):
                    positions = json.loads(positions)
                
                return [
                    PositionItem(
                        symbol=p.get("symbol", "BTC/USDT"),
                        side=p.get("side", "long"),
                        size=abs(p.get("size", 0)),
                        entryPrice=p.get("entry_price", 0),
                        leverage=p.get("leverage", 1),
                        pnl=p.get("pnl", 0),
                        stopLoss=p.get("stop_loss"),
                        takeProfit=p.get("take_profit"),
                    )
                    for p in positions
                ]
        except Exception:
            pass
    
    if _is_mock_mode():
        return _mock_positions()
    
    return []


async def _build_news(state: Dict[str, Any]) -> List[NewsItem]:
    """构建新闻列表"""
    news_data = state.get("news", [])
    
    if news_data:
        return [
            NewsItem(
                id=n.get("id", ""),
                title=n.get("title", ""),
                content=n.get("content", ""),
                source=n.get("source", "unknown"),
                sentiment=n.get("sentiment", "neutral"),
                sentiment_score=0.5,
                published=int(datetime.utcnow().timestamp()),
                url=n.get("url"),
            )
            for n in news_data[:10]
        ]
    
    redis = None
    try:
        redis = get_redis_client()
    except Exception:
        pass
    
    if redis:
        try:
            import json
            news_items = await redis.lrange("news:latest", 0, 9)
            
            if news_items:
                result = []
                for item in news_items:
                    if isinstance(item, str):
                        n = json.loads(item)
                    else:
                        n = item
                    
                    result.append(NewsItem(
                        id=n.get("id", ""),
                        title=n.get("title", ""),
                        content=n.get("content", ""),
                        source=n.get("source", "unknown"),
                        sentiment=n.get("sentiment", "neutral"),
                        sentiment_score=n.get("sentiment_score", 0.5),
                        published=n.get("published", int(datetime.utcnow().timestamp())),
                        url=n.get("url"),
                    ))
                return result
        except Exception:
            pass
    
    if _is_mock_mode():
        return _mock_news()
    
    return []


async def _get_weight_versions() -> List[WeightVersion]:
    """获取权重版本"""
    redis = None
    try:
        redis = get_redis_client()
    except Exception:
        pass
    
    if redis:
        try:
            import json
            versions_data = await redis.get("weights:versions")
            if versions_data:
                if isinstance(versions_data, str):
                    versions_data = json.loads(versions_data)
                return [
                    WeightVersion(
                        version=v.get("version", ""),
                        timestamp=v.get("timestamp", ""),
                        weights=v.get("weights", {}),
                        author=v.get("author", "system")
                    )
                    for v in versions_data
                ]
        except Exception:
            pass
    
    if _is_mock_mode():
        return [
            WeightVersion(
                version="v1.2.3",
                timestamp=datetime.utcnow().isoformat(),
                weights={"trend": 0.3, "momentum": 0.25, "volatility": 0.2, "sentiment": 0.15, "flow": 0.1},
                author="system"
            ),
        ]
    
    return []


async def _get_data_sources() -> List[DataSourceStatus]:
    """获取数据源状态"""
    redis = None
    try:
        redis = get_redis_client()
    except Exception:
        pass
    
    if redis:
        try:
            import json
            sources_data = await redis.get("data_sources:status")
            if sources_data:
                if isinstance(sources_data, str):
                    sources_data = json.loads(sources_data)
                return [
                    DataSourceStatus(
                        name=s.get("name", ""),
                        status=s.get("status", "unknown"),
                        lastUpdate=s.get("last_update", ""),
                        recordsCount=s.get("records_count", 0)
                    )
                    for s in sources_data
                ]
        except Exception:
            pass
    
    if _is_mock_mode():
        return [
            DataSourceStatus(
                name="Binance",
                status="online",
                lastUpdate=datetime.utcnow().isoformat(),
                recordsCount=12456
            ),
            DataSourceStatus(
                name="CryptoNews",
                status="online",
                lastUpdate=datetime.utcnow().isoformat(),
                recordsCount=8543
            ),
        ]
    
    return []


async def _get_traders() -> List[TraderItem]:
    """获取交易者列表"""
    redis = None
    try:
        redis = get_redis_client()
    except Exception:
        pass
    
    if redis:
        try:
            import json
            traders_data = await redis.get("traders:top")
            if traders_data:
                if isinstance(traders_data, str):
                    traders_data = json.loads(traders_data)
                return [
                    TraderItem(
                        id=t.get("id", ""),
                        name=t.get("name", ""),
                        platform=t.get("platform", ""),
                        followers=t.get("followers", 0),
                        sentiment=t.get("sentiment", 0.5),
                        recentPosition=t.get("recent_position", ""),
                        symbol=t.get("symbol", ""),
                        winRate=t.get("win_rate", 0.0)
                    )
                    for t in traders_data
                ]
        except Exception:
            pass
    
    if _is_mock_mode():
        return [
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
        ]
    
    return []


async def _get_social_posts() -> List[SocialPost]:
    """获取社交帖子"""
    redis = None
    try:
        redis = get_redis_client()
    except Exception:
        pass
    
    if redis:
        try:
            import json
            posts_data = await redis.get("social:posts:recent")
            if posts_data:
                if isinstance(posts_data, str):
                    posts_data = json.loads(posts_data)
                return [
                    SocialPost(
                        id=p.get("id", ""),
                        platform=p.get("platform", ""),
                        author=p.get("author", ""),
                        content=p.get("content", ""),
                        sentiment=p.get("sentiment", 0.5),
                        likes=p.get("likes", 0),
                        time=p.get("time", ""),
                        timestamp=p.get("timestamp", ""),
                        symbols=p.get("symbols", [])
                    )
                    for p in posts_data
                ]
        except Exception:
            pass
    
    if _is_mock_mode():
        return [
            SocialPost(
                id="post_1",
                platform="twitter",
                author="CryptoWatcher",
                content="BTC looking strong! Expecting a breakout soon",
                sentiment=0.75,
                likes=1245,
                time="2h ago",
                timestamp=datetime.utcnow().isoformat(),
                symbols=["BTC", "ETH"]
            ),
        ]
    
    return []


async def _get_macro() -> Optional[MacroData]:
    """获取宏观数据"""
    redis = None
    try:
        redis = get_redis_client()
    except Exception:
        pass
    
    if redis:
        try:
            import json
            macro_data = await redis.get("macro:data")
            if macro_data:
                if isinstance(macro_data, str):
                    macro_data = json.loads(macro_data)
                return MacroData(
                    gold=macro_data.get("gold", {"price": 0, "change": 0}),
                    usd_index=macro_data.get("usd_index", {"value": 0, "change": 0}),
                    oil=macro_data.get("oil", {"price": 0, "change": 0})
                )
        except Exception:
            pass
    
    if _is_mock_mode():
        return MacroData(
            gold={"price": 2028.5, "change": 0.8},
            usd_index={"value": 103.2, "change": -0.3},
            oil={"price": 78.45, "change": 1.2}
        )
    
    return None


async def _get_fear_greed() -> Optional[FearGreedData]:
    """获取恐慌贪婪指数"""
    redis = None
    try:
        redis = get_redis_client()
    except Exception:
        pass
    
    if redis:
        try:
            import json
            fg_data = await redis.get("fear_greed:index")
            if fg_data:
                if isinstance(fg_data, str):
                    fg_data = json.loads(fg_data)
                return FearGreedData(
                    value=fg_data.get("value", 0),
                    classification=fg_data.get("classification", "Unknown"),
                    timestamp=fg_data.get("timestamp", "")
                )
        except Exception:
            pass
    
    if _is_mock_mode():
        return FearGreedData(
            value=55,
            classification="Neutral",
            timestamp=datetime.utcnow().isoformat()
        )
    
    return None


async def _get_etf() -> Optional[EtfData]:
    """获取 ETF 数据"""
    redis = None
    try:
        redis = get_redis_client()
    except Exception:
        pass
    
    if redis:
        try:
            import json
            etf_data = await redis.get("etf:flow")
            if etf_data:
                if isinstance(etf_data, str):
                    etf_data = json.loads(etf_data)
                return EtfData(
                    symbol=etf_data.get("symbol", ""),
                    net_flow=etf_data.get("net_flow", 0),
                    inflow=etf_data.get("inflow", 0),
                    outflow=etf_data.get("outflow", 0),
                    confidence=etf_data.get("confidence", 0.0)
                )
        except Exception:
            pass
    
    if _is_mock_mode():
        return EtfData(
            symbol="BTC ETF",
            net_flow=125000000,
            inflow=180000000,
            outflow=55000000,
            confidence=0.85
        )
    
    return None


# ============================================
# Mock Data Functions
# ============================================

def _mock_prices() -> List[PriceItem]:
    """Mock 价格数据"""
    return [
        PriceItem(
            symbol="BTC/USDT",
            price=80724.5,
            change24h=0.025,
            volume_24h=1500000000.0,
            exchange="binance"
        ),
        PriceItem(
            symbol="ETH/USDT",
            price=2262.62,
            change24h=-0.015,
            volume_24h=800000000.0,
            exchange="binance"
        ),
        PriceItem(
            symbol="SOL/USDT",
            price=91.47,
            change24h=0.032,
            volume_24h=300000000.0,
            exchange="binance"
        ),
    ]


def _mock_factors() -> List[FactorItem]:
    """Mock 因子数据"""
    return [
        FactorItem(
            type="trend",
            name="趋势因子",
            nameEn="Trend Factor",
            weight=0.25,
            value=0.65,
            confidence=78,
            color="blue"
        ),
        FactorItem(
            type="momentum",
            name="动量因子",
            nameEn="Momentum Factor",
            weight=0.25,
            value=0.72,
            confidence=82,
            color="green"
        ),
        FactorItem(
            type="volatility",
            name="波动率因子",
            nameEn="Volatility Factor",
            weight=0.2,
            value=0.45,
            confidence=65,
            color="orange"
        ),
        FactorItem(
            type="sentiment",
            name="情绪因子",
            nameEn="Sentiment Factor",
            weight=0.15,
            value=0.58,
            confidence=71,
            color="purple"
        ),
        FactorItem(
            type="flow",
            name="资金流因子",
            nameEn="Flow Factor",
            weight=0.15,
            value=0.38,
            confidence=59,
            color="cyan"
        ),
    ]


def _mock_positions() -> List[PositionItem]:
    """Mock 持仓数据"""
    return [
        PositionItem(
            symbol="BTC/USDT",
            side="long",
            size=0.5,
            entryPrice=78500.0,
            leverage=3,
            pnl=1367.28,
            stopLoss=76000.0,
            takeProfit=85000.0
        ),
        PositionItem(
            symbol="ETH/USDT",
            side="long",
            size=5.0,
            entryPrice=2200.0,
            leverage=2,
            pnl=728.35,
            stopLoss=2100.0,
            takeProfit=2500.0
        ),
    ]


def _mock_news() -> List[NewsItem]:
    """Mock 新闻数据"""
    return [
        NewsItem(
            id="news_1",
            title="Bitcoin Breaks $80K Resistance Level",
            content="Bitcoin has successfully broken through the $80,000 resistance level...",
            source="CryptoNews",
            sentiment="bullish",
            sentiment_score=0.75,
            published=int(datetime.utcnow().timestamp()),
            url="https://example.com/news/1"
        ),
        NewsItem(
            id="news_2",
            title="Ethereum 2.0 Staking Reaches New High",
            content="Ethereum 2.0 staking deposits have reached a new all-time high...",
            source="CoinDesk",
            sentiment="bullish",
            sentiment_score=0.68,
            published=int(datetime.utcnow().timestamp()) - 3600,
            url="https://example.com/news/2"
        ),
    ]
