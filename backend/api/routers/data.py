"""
Data Router - Data API Endpoints (Read-only from Redis)
Migrated from infrastructure/data_api
"""
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

import logging
from application.queries.service_queries import get_redis_client_sync

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/data", tags=["Data"])


class PriceResponse(BaseModel):
    symbol: str
    price: float
    change_24h: float
    volume_24h: float
    exchange: str
    timestamp: datetime


class ETFResponse(BaseModel):
    symbol: str
    net_flow: float
    inflow: float
    outflow: float
    aum: float
    sources: List[str]
    confidence: float
    timestamp: datetime


class NewsResponse(BaseModel):
    id: str
    title: str
    content: str
    source: str
    sentiment: str
    sentiment_score: float
    event_type: str
    black_swan_score: float
    urgency: str
    affected_symbols: List[str]
    is_black_swan: bool
    published: int
    timestamp: datetime


class MacroResponse(BaseModel):
    asset: str
    name: str
    price: float
    change_1d: float
    change_7d: float
    unit: str
    sources: List[str]
    timestamp: datetime


class TraderOpinionResponse(BaseModel):
    trader_id: str
    trader_name: str
    platform: str
    content: str
    sentiment: str
    sentiment_score: float
    mentioned_assets: List[str]
    time_horizon: str
    influence_score: float
    published: int
    timestamp: datetime


class AggregateSentimentResponse(BaseModel):
    sentiment: str
    score: float
    count: int
    bullish_count: int
    bearish_count: int
    timestamp: datetime


def _get_redis():
    try:
        return get_redis_client_sync()
    except Exception as e:
        logger.warning(f"Redis not available: {e}")
        return None


@router.get("/prices/{symbol}", response_model=Optional[PriceResponse])
async def get_price(
    symbol: str,
    exchange: str = Query(default="binance", description="Exchange name")
):
    """Get single symbol price from Redis cache"""
    redis = _get_redis()
    if not redis:
        return None

    try:
        price_key = f"price:{symbol}:{exchange}"
        price_data = await redis.get(price_key)

        if price_data:
            if isinstance(price_data, str):
                import json
                price_data = json.loads(price_data)

            return PriceResponse(
                symbol=symbol,
                price=price_data.get("price", 0),
                change_24h=price_data.get("change_24h", 0),
                volume_24h=price_data.get("volume_24h", 0),
                exchange=exchange,
                timestamp=datetime.now()
            )
    except Exception as e:
        logger.error(f"Error getting price from Redis: {e}")

    return None


@router.get("/prices", response_model=List[PriceResponse])
async def get_all_prices(
    symbols: Optional[str] = Query(default=None, description="Comma-separated symbols")
):
    """Get all prices from Redis cache"""
    redis = _get_redis()
    if not redis:
        return []

    symbol_list = symbols.split(",") if symbols else ["BTC", "ETH", "SOL", "DOGE"]
    results = []

    try:
        for symbol in symbol_list:
            for exchange in ["binance", "coingecko"]:
                price_key = f"price:{symbol}:{exchange}"
                price_data = await redis.get(price_key)

                if price_data:
                    if isinstance(price_data, str):
                        import json
                        price_data = json.loads(price_data)

                    results.append(PriceResponse(
                        symbol=symbol,
                        price=price_data.get("price", 0),
                        change_24h=price_data.get("change_24h", 0),
                        volume_24h=price_data.get("volume_24h", 0),
                        exchange=exchange,
                        timestamp=datetime.now()
                    ))
                    break
    except Exception as e:
        logger.error(f"Error getting prices from Redis: {e}")

    return results


@router.get("/etf/{symbol}", response_model=Optional[ETFResponse])
async def get_etf_flow(symbol: str = "BTC"):
    """Get ETF flow data from Redis cache"""
    redis = _get_redis()
    if not redis:
        return None

    try:
        etf_key = f"etf:{symbol}:flow"
        etf_data = await redis.get(etf_key)

        if etf_data:
            if isinstance(etf_data, str):
                import json
                etf_data = json.loads(etf_data)

            return ETFResponse(
                symbol=symbol,
                net_flow=etf_data.get("net_flow", 0),
                inflow=etf_data.get("inflow", 0),
                outflow=etf_data.get("outflow", 0),
                aum=etf_data.get("aum", 0),
                sources=etf_data.get("sources", []),
                confidence=etf_data.get("confidence", 0),
                timestamp=datetime.now()
            )
    except Exception as e:
        logger.error(f"Error getting ETF data from Redis: {e}")

    return None


@router.get("/news", response_model=List[NewsResponse])
async def get_latest_news(
    limit: int = Query(default=20, le=100),
    sentiment: Optional[str] = Query(default=None),
    include_black_swan: bool = Query(default=True)
):
    """Get latest news from Redis cache"""
    redis = _get_redis()
    if not redis:
        return []

    try:
        news_key = f"news:{sentiment or 'all'}:{limit}"
        news_list = await redis.get(news_key)

        if news_list:
            if isinstance(news_list, str):
                import json
                news_list = json.loads(news_list)

            results = []
            for item in news_list[:limit]:
                try:
                    results.append(NewsResponse(
                        id=item.get("id", ""),
                        title=item.get("title", ""),
                        content=item.get("content", ""),
                        source=item.get("source", ""),
                        sentiment=item.get("sentiment", "neutral"),
                        sentiment_score=item.get("sentiment_score", 0),
                        event_type=item.get("event_type", ""),
                        black_swan_score=item.get("black_swan_score", 0),
                        urgency=item.get("urgency", ""),
                        affected_symbols=item.get("affected_symbols", []),
                        is_black_swan=item.get("black_swan", False),
                        published=item.get("published_at", 0),
                        timestamp=datetime.now()
                    ))
                except Exception as e:
                    logger.warning(f"Error parsing news item: {e}")
                    continue

            return results
    except Exception as e:
        logger.error(f"Error getting news from Redis: {e}")

    return []


@router.get("/news/black-swan", response_model=List[NewsResponse])
async def get_black_swan_news():
    """Get black swan news from Redis cache"""
    return await get_latest_news(limit=10, include_black_swan=True)


@router.get("/macro", response_model=List[MacroResponse])
async def get_macro_data(asset: Optional[str] = Query(default=None)):
    """Get macro data from Redis cache"""
    redis = _get_redis()
    if not redis:
        return []

    try:
        results = []
        assets = [asset] if asset else ["BTC", "ETH", "SOL"]

        for asset_name in assets:
            macro_key = f"macro:{asset_name}"
            macro_data = await redis.get(macro_key)

            if macro_data:
                if isinstance(macro_data, str):
                    import json
                    macro_data = json.loads(macro_data)

                results.append(MacroResponse(
                    asset=asset_name,
                    name=macro_data.get("name", asset_name),
                    price=macro_data.get("price", 0),
                    change_1d=macro_data.get("change_1d", 0),
                    change_7d=macro_data.get("change_7d", 0),
                    unit=macro_data.get("unit", ""),
                    sources=macro_data.get("sources", []),
                    timestamp=datetime.now()
                ))

        return results
    except Exception as e:
        logger.error(f"Error getting macro data from Redis: {e}")

    return []


@router.get("/trader-opinions", response_model=List[TraderOpinionResponse])
async def get_trader_opinions(
    asset: Optional[str] = Query(default=None),
    sentiment: Optional[str] = Query(default=None)
):
    """Get trader opinions from Redis cache"""
    redis = _get_redis()
    if not redis:
        return []

    try:
        key = f"trader:opinions:{asset or 'all'}:{sentiment or 'all'}"
        opinions = await redis.get(key)

        if opinions:
            if isinstance(opinions, str):
                import json
                opinions = json.loads(opinions)

            return [TraderOpinionResponse(**op) for op in opinions]
    except Exception as e:
        logger.error(f"Error getting trader opinions from Redis: {e}")

    return []


@router.get("/sentiment/aggregate", response_model=AggregateSentimentResponse)
async def get_aggregate_sentiment():
    """Get aggregate sentiment from Redis cache"""
    redis = _get_redis()
    if not redis:
        return AggregateSentimentResponse(
            sentiment="unknown",
            score=0,
            count=0,
            bullish_count=0,
            bearish_count=0,
            timestamp=datetime.now()
        )

    try:
        sentiment_key = "trader:sentiment:aggregate"
        sentiment = await redis.get(sentiment_key)

        if sentiment:
            if isinstance(sentiment, str):
                import json
                sentiment = json.loads(sentiment)

            return AggregateSentimentResponse(
                sentiment=sentiment.get("sentiment", "neutral"),
                score=sentiment.get("score", 0),
                count=sentiment.get("count", 0),
                bullish_count=sentiment.get("bullish_count", 0),
                bearish_count=sentiment.get("bearish_count", 0),
                timestamp=datetime.now()
            )
    except Exception as e:
        logger.error(f"Error getting aggregate sentiment from Redis: {e}")

    return AggregateSentimentResponse(
        sentiment="unknown",
        score=0,
        count=0,
        bullish_count=0,
        bearish_count=0,
        timestamp=datetime.now()
    )


@router.get("/crypto-stocks")
async def get_crypto_stocks():
    """Get crypto-related stocks from Redis cache"""
    redis = _get_redis()
    if not redis:
        return []

    try:
        stocks_key = "crypto_stocks:all"
        stocks = await redis.get(stocks_key)

        if stocks:
            if isinstance(stocks, str):
                import json
                stocks = json.loads(stocks)
            return stocks
    except Exception as e:
        logger.error(f"Error getting crypto stocks from Redis: {e}")

    return []
