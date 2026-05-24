import os
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from application.queries.infrastructure_queries import get_redis_client_sync
from application.queries.projection import get_projection_reader
import logging

logger = logging.getLogger(__name__)


_factors: Dict[str, Dict] = {}
_proposals: List[Dict] = []
_snapshots: List[Dict] = []
_factor_lineage: List[Dict] = []


def _is_mock_mode() -> bool:
    return os.getenv("DASHBOARD_MOCK", "false").lower() == "true"


def _init_mock_factors():
    global _factors
    _factors = {
        "trend": {
            "type": "trend",
            "name": "趋势因子",
            "nameEn": "Trend Factor",
            "weight": 0.25,
            "value": 0.65,
            "confidence": 78,
            "color": "blue"
        },
        "momentum": {
            "type": "momentum",
            "name": "动量因子",
            "nameEn": "Momentum Factor",
            "weight": 0.25,
            "value": 0.72,
            "confidence": 82,
            "color": "green"
        },
        "volatility": {
            "type": "volatility",
            "name": "波动率因子",
            "nameEn": "Volatility Factor",
            "weight": 0.20,
            "value": 0.45,
            "confidence": 65,
            "color": "orange"
        },
        "sentiment": {
            "type": "sentiment",
            "name": "情绪因子",
            "nameEn": "Sentiment Factor",
            "weight": 0.15,
            "value": 0.58,
            "confidence": 71,
            "color": "purple"
        },
        "flow": {
            "type": "flow",
            "name": "资金流因子",
            "nameEn": "Flow Factor",
            "weight": 0.15,
            "value": 0.38,
            "confidence": 59,
            "color": "cyan"
        }
    }


if _is_mock_mode():
    _init_mock_factors()


def _get_storage_factors():
    return _factors


def _get_storage_proposals():
    return _proposals


def _get_storage_snapshots():
    return _snapshots


def _get_storage_factor_lineage():
    return _factor_lineage


def _mock_prices() -> List[Any]:
    from api.schemas import PriceItem
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


def _mock_factors() -> List[Any]:
    from api.schemas import FactorItem
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


def _mock_positions() -> List[Any]:
    from api.schemas import PositionItem
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


def _mock_news() -> List[Any]:
    from api.schemas import NewsItem
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


async def _build_prices(state: Dict[str, Any]) -> List[Any]:
    from api.schemas import PriceItem
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
        redis = get_redis_client_sync()
    except Exception:
        pass

    if redis:
        try:
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


async def _build_factors(state: Dict[str, Any]) -> List[Any]:
    from api.schemas import FactorItem
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

    factors_raw = _get_storage_factors()
    if factors_raw:
        return [FactorItem(**f) for f in factors_raw.values()]

    if _is_mock_mode():
        return _mock_factors()

    return []


async def _build_regime(state: Dict[str, Any]) -> Any:
    from api.schemas import RegimeState
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


async def _build_risk(reader) -> Any:
    from api.schemas import RiskIndex, RiskComponent
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


async def _build_signal(state: Dict[str, Any]) -> Any:
    from api.schemas import Signal
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


async def _build_positions(reader) -> List[Any]:
    from api.schemas import PositionItem
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

    if _is_mock_mode():
        return _mock_positions()

    return []


async def _build_news(state: Dict[str, Any]) -> List[Any]:
    from api.schemas import NewsItem
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

    if _is_mock_mode():
        return _mock_news()

    return []


async def _get_weight_versions() -> List[Any]:
    from api.schemas import WeightVersion
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


async def _get_data_sources() -> List[Any]:
    from api.schemas import DataSourceStatus
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


async def _get_traders() -> List[Any]:
    from api.schemas import TraderItem
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


async def _get_social_posts() -> List[Any]:
    from api.schemas import SocialPost
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


async def _get_macro() -> Optional[Any]:
    from api.schemas import MacroData
    if _is_mock_mode():
        return MacroData(
            gold={"price": 2028.5, "change": 0.8},
            usd_index={"value": 103.2, "change": -0.3},
            oil={"price": 78.45, "change": 1.2}
        )

    return None


async def _get_fear_greed() -> Optional[Any]:
    from api.schemas import FearGreedData
    if _is_mock_mode():
        return FearGreedData(
            value=55,
            classification="Neutral",
            timestamp=datetime.utcnow().isoformat()
        )

    return None


async def _get_etf() -> Optional[Any]:
    from api.schemas import EtfData
    if _is_mock_mode():
        return EtfData(
            symbol="BTC ETF",
            net_flow=125000000,
            inflow=180000000,
            outflow=55000000,
            confidence=0.85
        )

    return None


_dashboard_service_instance = None


def get_dashboard_service():
    global _dashboard_service_instance
    if _dashboard_service_instance is None:
        _dashboard_service_instance = type("DashboardService", (), {
            "get_overview": lambda self, **kw: _get_overview_data(**kw),
            "get_prices": lambda self, **kw: _mock_prices(),
            "get_factors": lambda self, **kw: _mock_factors(),
            "get_positions": lambda self, **kw: _mock_positions(),
            "get_news": lambda self, **kw: _mock_news(),
        })()
    return _dashboard_service_instance


def _get_overview_data(**kwargs):
    symbol = kwargs.get("symbol", "BTCUSDT")
    return {
        "symbol": symbol,
        "price": _mock_prices(),
        "factors": _mock_factors(),
        "positions": _mock_positions(),
        "news": _mock_news(),
    }


async def get_dashboard_overview(symbol: str) -> Dict[str, Any]:
    service = get_dashboard_service()
    return await service.get_overview(symbol=symbol)


async def get_dashboard_signals(symbol: str, limit: int = 20) -> Any:
    service = get_dashboard_service()
    return await service.get_signals(symbol=symbol, limit=limit)


async def get_dashboard_positions(symbol: str) -> Any:
    service = get_dashboard_service()
    return await service.get_positions(symbol=symbol)


async def get_dashboard_performance(symbol: str, period: str = "24h") -> Any:
    service = get_dashboard_service()
    return await service.get_performance(symbol=symbol, period=period)


async def get_dashboard_risk(symbol: str) -> Any:
    service = get_dashboard_service()
    return await service.get_risk(symbol=symbol)


async def get_dashboard_news(symbol: str, page: int = 1, page_size: int = 10) -> Any:
    service = get_dashboard_service()
    return await service.get_news(symbol=symbol, page=page, page_size=page_size)


async def get_dashboard_social_posts(symbol: str, page: int = 1, page_size: int = 10) -> Any:
    service = get_dashboard_service()
    return await service.get_social_posts(symbol=symbol, page=page, page_size=page_size)


async def get_dashboard_high_frequency_data(symbol: str) -> Any:
    service = get_dashboard_service()
    return await service.get_high_frequency_data(symbol=symbol)


async def get_dashboard_low_frequency_data(symbol: str) -> Any:
    service = get_dashboard_service()
    return await service.get_low_frequency_data(symbol=symbol)


async def get_dashboard_market_data(symbol: str) -> Any:
    service = get_dashboard_service()
    return await service.get_market_data(symbol=symbol)


async def get_dashboard_strategy_status(symbol: str) -> Any:
    service = get_dashboard_service()
    return await service.get_strategy_status(symbol=symbol)


async def get_dashboard_correlation_summary(symbol: str) -> Any:
    service = get_dashboard_service()
    return await service.get_correlation_summary(symbol=symbol)


async def get_dashboard_factor_summary(symbol: str) -> Any:
    service = get_dashboard_service()
    return await service.get_factor_summary(symbol=symbol)


async def _get_price_from_redis(symbol: str, exchange: str) -> Optional[Dict[str, Any]]:
    redis = get_redis_client_sync()
    if not redis:
        return None

    try:
        price_key = f"price:{symbol}:{exchange}"
        price_data = await redis.get(price_key)

        if price_data:
            if isinstance(price_data, str):
                price_data = json.loads(price_data)
            return price_data
    except Exception as e:
        logger.error(f"Error getting price from Redis: {e}")

    return None


async def get_price_comparison(symbol: str) -> Any:
    from api.schemas import PriceComparisonResponse
    if _is_mock_mode():
        return PriceComparisonResponse(
            symbol=symbol,
            prices=[
                {"exchange": "Binance", "price": 62345.78, "bid": 62344.23, "ask": 62347.33, "volume": 28.5},
                {"exchange": "OKX", "price": 62348.12, "bid": 62346.5, "ask": 62349.74, "volume": 15.2},
                {"exchange": "Bybit", "price": 62343.9, "bid": 62342.5, "ask": 62345.3, "volume": 12.8}
            ],
            priceSpread=4.22,
            bestBid="Bybit",
            bestAsk="OKX",
            timestamp=datetime.now().isoformat()
        )

    prices = []
    exchanges = ["binance", "okx", "bybit", "coingecko"]

    for exchange in exchanges:
        price_data = await _get_price_from_redis(symbol, exchange)
        if price_data:
            prices.append({
                "exchange": exchange.capitalize(),
                "price": price_data.get("price", 0),
                "bid": price_data.get("bid", price_data.get("price", 0)),
                "ask": price_data.get("ask", price_data.get("price", 0)),
                "volume": price_data.get("volume_24h", 0),
            })

    if not prices:
        return PriceComparisonResponse(
            symbol=symbol,
            prices=[],
            priceSpread=0,
            bestBid="",
            bestAsk="",
            timestamp=datetime.now().isoformat()
        )

    price_values = [p["price"] for p in prices]
    price_spread = max(price_values) - min(price_values) if len(price_values) > 1 else 0

    best_bid = min(prices, key=lambda x: x["bid"])["exchange"] if prices else ""
    best_ask = max(prices, key=lambda x: x["ask"])["exchange"] if prices else ""

    return PriceComparisonResponse(
        symbol=symbol,
        prices=prices,
        priceSpread=price_spread,
        bestBid=best_bid,
        bestAsk=best_ask,
        timestamp=datetime.now().isoformat()
    )


async def get_price_source_status() -> Any:
    from api.schemas import PriceSourceStatusResponse
    if _is_mock_mode():
        return PriceSourceStatusResponse(
            sources={
                "Binance": {"status": "online", "lastUpdate": datetime.now().isoformat(), "latency": 45},
                "OKX": {"status": "online", "lastUpdate": datetime.now().isoformat(), "latency": 38},
                "Bybit": {"status": "online", "lastUpdate": datetime.now().isoformat(), "latency": 52}
            }
        )

    sources = {}
    exchanges = ["binance", "okx", "bybit", "coingecko"]
    for exchange in exchanges:
        price_data = await _get_price_from_redis("BTC", exchange)
        sources[exchange.capitalize()] = {
            "status": "online" if price_data else "offline",
            "lastUpdate": datetime.now().isoformat(),
            "latency": 0
        }

    return PriceSourceStatusResponse(sources=sources)


def get_all_proposals() -> List[Any]:
    from api.schemas import ProposalResponse
    proposals = _get_storage_proposals()
    return [
        ProposalResponse(
            id=p["id"],
            name=p["name"],
            description=p.get("description"),
            type=p["type"],
            status=p["status"],
            created_by=p["created_by"],
            created_at=p["created_at"],
            updated_at=p.get("updated_at", p["created_at"]),
            parameters=p.get("parameters", {}),
            backtest_results=p.get("backtest_results")
        ) for p in proposals
    ]


def create_proposal(request: Any) -> Any:
    from api.schemas import ProposalResponse
    proposal_id = f"prop_{uuid.uuid4().hex[:12]}"
    now = datetime.now().isoformat()
    proposal = {
        "id": proposal_id,
        "name": request.name,
        "description": request.description,
        "type": request.type,
        "status": "draft",
        "created_by": request.created_by,
        "created_at": now,
        "updated_at": now,
        "parameters": request.parameters
    }
    _get_storage_proposals().append(proposal)
    return ProposalResponse(
        id=proposal["id"],
        name=proposal["name"],
        description=proposal.get("description"),
        type=proposal["type"],
        status=proposal["status"],
        created_by=proposal["created_by"],
        created_at=proposal["created_at"],
        updated_at=proposal["updated_at"],
        parameters=proposal["parameters"]
    )


def update_proposal(proposal_id: str, request: Any) -> Optional[Any]:
    from api.schemas import ProposalResponse
    proposals = _get_storage_proposals()
    for p in proposals:
        if p["id"] == proposal_id:
            if request.name:
                p["name"] = request.name
            if request.description:
                p["description"] = request.description
            if request.type:
                p["type"] = request.type
            if request.status:
                p["status"] = request.status
            if request.parameters:
                p["parameters"] = request.parameters
            p["updated_at"] = datetime.now().isoformat()
            return ProposalResponse(
                id=p["id"],
                name=p["name"],
                description=p.get("description"),
                type=p["type"],
                status=p["status"],
                created_by=p["created_by"],
                created_at=p["created_at"],
                updated_at=p["updated_at"],
                parameters=p["parameters"]
            )
    return None


def get_all_snapshots() -> List[Any]:
    from api.schemas import SnapshotResponse
    snapshots = _get_storage_snapshots()
    return [
        SnapshotResponse(
            id=s["id"],
            timestamp=s["timestamp"],
            name=s.get("name"),
            type=s["type"],
            data=s["data"],
            description=s.get("description")
        ) for s in snapshots
    ]


def create_snapshot(request: Any) -> Any:
    from api.schemas import SnapshotResponse
    snapshot_id = f"snap_{uuid.uuid4().hex[:12]}"
    factors = _get_storage_factors()
    snapshot = {
        "id": snapshot_id,
        "timestamp": datetime.now().isoformat(),
        "name": request.name,
        "type": request.type,
        "data": request.data or {"factors": factors.copy()},
        "description": request.description
    }
    _get_storage_snapshots().insert(0, snapshot)
    return SnapshotResponse(
        id=snapshot["id"],
        timestamp=snapshot["timestamp"],
        name=snapshot.get("name"),
        type=snapshot["type"],
        data=snapshot["data"],
        description=snapshot.get("description")
    )


def get_factor_lineage() -> List[Any]:
    from api.schemas import FactorLineageEntry
    lineage = _get_storage_factor_lineage()
    return [
        FactorLineageEntry(
            id=e["id"],
            factor_type=e["factor_type"],
            timestamp=e["timestamp"],
            change_type=e["change_type"],
            old_value=e["old_value"],
            new_value=e["new_value"],
            reason=e["reason"],
            user=e.get("user"),
            related_proposal_id=e.get("related_proposal_id")
        ) for e in lineage
    ]


def get_all_factors() -> List[Any]:
    from api.schemas import FactorItem
    factors = _get_storage_factors()
    return [FactorItem(**f) for f in factors.values()]


def get_factor(factor_type: str) -> Optional[Any]:
    from api.schemas import FactorItem
    factors = _get_storage_factors()
    f = factors.get(factor_type)
    return FactorItem(**f) if f else None


def update_factor_weight(factor_type: str, weight: float) -> Any:
    from api.schemas import SuccessResponse
    factors = _get_storage_factors()
    if factor_type not in factors:
        return SuccessResponse(success=False, message="Factor not found")

    old_weight = factors[factor_type]["weight"]

    factors[factor_type]["weight"] = weight

    _get_storage_factor_lineage().append({
        "id": f"lineage_{uuid.uuid4().hex[:12]}",
        "factor_type": factor_type,
        "timestamp": datetime.now().isoformat(),
        "change_type": "weight_update",
        "old_value": old_weight,
        "new_value": weight,
        "reason": "Manual weight update",
        "user": "api"
    })

    return SuccessResponse(success=True, message=f"{factor_type} weight updated successfully")
