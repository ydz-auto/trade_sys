"""
TradeAgent Data Service
数据采集服务 - 主入口
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from infrastructure.logging import get_logger
logger = get_logger("data_service.main")

from shared.config import get_datasource_config_manager, API_GATEWAY_CONFIGS
from shared.state import get_system_state_manager

from .collectors import (
    ExchangeCollector,
    ETFCollector,
    NewsCollector,
    MacroCollector,
    SocialMediaCollector,
    CryptoStockCollector,
    TraderDataCollector,
)
from .websocket import ws_manager
from .kafka_producer import kafka_producer
from .cache import DataServiceCache, get_data_cache
from .storage import DataStorage, data_storage
from .tdp_adapter import TDPAdapter, TDPPriceData, TDPNewsData, TDPEtfData, TDPTraderOpinion, get_tdp_adapter
from infrastructure.cache import init_redis, close_redis
from infrastructure.webhook.receiver import WebhookReceiver, WebhookSource

SERVICE_NAME = "data_service"
ds_config = get_datasource_config_manager()

SYMBOLS = ds_config.get_symbols()
EXCHANGES = ds_config.get_exchanges()

collectors: Dict[str, Any] = {}
data_cache: Optional[DataServiceCache] = None
tdp_adapter: Optional[TDPAdapter] = None

CHECK_INTERVAL = ds_config.get_check_interval()
NEWS_INTERVAL = ds_config.get_news_check_interval()


class HealthResponse(BaseModel):
    status: str
    service: str
    symbols: List[str]
    exchanges: List[str]
    redis_connected: bool
    kafka_connected: bool
    clickhouse_connected: bool
    collectors: Dict[str, Dict[str, Any]]


class PriceResponse(BaseModel):
    symbol: str
    exchange: str
    price: float
    bid: float
    ask: float
    spread: float
    volume_24h: float
    change_24h: float
    timestamp: str


class NewsWebhookPayload(BaseModel):
    source: str
    event_type: str
    data: Dict[str, Any]


@asynccontextmanager
async def lifespan(app: FastAPI):
    global collectors, data_cache, tdp_adapter

    logger.info("Starting Data Service...")

    await kafka_producer.connect()
    await init_redis()
    data_cache = get_data_cache()
    await data_storage.initialize()

    tdp_adapter = get_tdp_adapter()
    tdp_adapter.set_publisher(kafka_producer)

    collectors = {
        "exchange": ExchangeCollector(SYMBOLS, EXCHANGES),
        "etf": ETFCollector(),
        "news": NewsCollector(),
        "macro": MacroCollector(),
        "social": SocialMediaCollector(),
        "crypto_stock": CryptoStockCollector(),
        "trader": TraderDataCollector(),
    }

    asyncio.create_task(run_data_collection())
    asyncio.create_task(run_news_collection())

    state_manager = get_system_state_manager()
    await state_manager.update({"status": "RUNNING"})
    logger.info("Data Service started successfully")

    yield

    logger.info("Shutting down Data Service...")
    await kafka_producer.disconnect()
    await close_redis()
    await state_manager.update({"status": "STOPPED"})
    logger.info("Data Service stopped")


app = FastAPI(
    title="TradeAgent Data Service",
    version="1.0.0",
    description="Market data collection and distribution service",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health():
    redis_ok = False
    kafka_ok = kafka_producer.is_connected if hasattr(kafka_producer, 'is_connected') else True
    clickhouse_ok = data_storage._initialized if hasattr(data_storage, '_initialized') else False

    try:
        if data_cache:
            redis_ok = await data_cache._cache.redis.ping()
    except:
        pass

    collector_status = {}
    for name, collector in collectors.items():
        status = "unknown"
        last_run = None
        items_count = 0
        circuit_state = None

        if hasattr(collector, "last_collect_time"):
            last_run = collector.last_collect_time.isoformat() if collector.last_collect_time else None
        if hasattr(collector, "get_item_count"):
            items_count = collector.get_item_count()
        if hasattr(collector, "get_status"):
            collector_info = collector.get_status()
            circuit_state = collector_info.get("resilience", {}).get("circuit_breaker", {})

        status = "running" if last_run else "pending"

        collector_status[name] = {
            "status": status,
            "last_run": last_run,
            "items_count": items_count,
            "circuit_state": circuit_state.get("state") if circuit_state else None
        }

    overall_status = "ok" if (redis_ok and kafka_ok and clickhouse_ok) else "degraded"

    return HealthResponse(
        status=overall_status,
        service=SERVICE_NAME,
        symbols=SYMBOLS,
        exchanges=EXCHANGES,
        redis_connected=redis_ok,
        kafka_connected=kafka_ok,
        clickhouse_connected=clickhouse_ok,
        collectors=collector_status
    )


@app.get("/api/v1/data/price/{symbol}", response_model=PriceResponse)
async def get_price(symbol: str, exchange: str = "binance"):
    if "exchange" not in collectors:
        raise HTTPException(status_code=503, detail="Service not initialized")

    cached = await data_cache.get_price(symbol.upper(), exchange) if data_cache else None
    if cached:
        return cached

    price_data = await collectors["exchange"].get_price_for_trading(symbol.upper(), exchange)
    if price_data:
        result = {
            "symbol": symbol.upper(),
            "exchange": exchange,
            "price": price_data.price,
            "bid": price_data.bid,
            "ask": price_data.ask,
            "spread": price_data.spread,
            "volume_24h": price_data.volume_24h,
            "change_24h": price_data.change_24h,
            "timestamp": price_data.timestamp.isoformat()
        }
        if data_cache:
            await data_cache.set_price(symbol.upper(), exchange, result)
        return result
    raise HTTPException(status_code=404, detail="Price not found")


@app.get("/api/v1/data/prices")
async def get_all_prices(use_cache: bool = True):
    if "exchange" not in collectors:
        raise HTTPException(status_code=503, detail="Service not initialized")

    if use_cache and data_cache:
        cached_data = {}
        cache_hits = 0
        for symbol in SYMBOLS:
            cached = await data_cache.get_all_prices(symbol)
            if cached:
                cached_data[symbol] = cached
                cache_hits += 1

        if cache_hits > len(SYMBOLS) // 2:
            return {"prices": cached_data, "source": "cache", "cache_hits": cache_hits}

    await collectors["exchange"].collect()
    result = {}

    for symbol in SYMBOLS:
        multi_prices = collectors["exchange"].get_latest_prices(symbol)
        if multi_prices:
            result[symbol] = {
                "exchanges": {
                    name: {
                        "price": p.price,
                        "change_24h": p.change_24h,
                        "volume_24h": p.volume_24h
                    }
                    for name, p in multi_prices.prices.items()
                    if p.status == "ok"
                }
            }
            if data_cache:
                await data_cache.set_all_prices(symbol, result[symbol])

    return {"prices": result, "source": "collector"}


@app.get("/api/v1/data/etf/{symbol}")
async def get_etf_flow(symbol: str):
    if "etf" not in collectors:
        raise HTTPException(status_code=503, detail="Service not initialized")

    cached = await data_cache.get_etf_flow(symbol.upper()) if data_cache else None
    if cached:
        return cached

    result = collectors["etf"].get_latest_flow(symbol.upper())
    if result:
        response = {
            "symbol": symbol.upper(),
            "net_flow": result.net_flow,
            "inflow": result.inflow,
            "outflow": result.outflow,
            "aum": result.aum,
            "sources": result.sources_used,
            "confidence": result.confidence,
            "timestamp": result.timestamp.isoformat()
        }
        if data_cache:
            await data_cache.set_etf_flow(symbol.upper(), response)
        return response
    raise HTTPException(status_code=404, detail="ETF data not found")


@app.get("/api/v1/data/macro")
async def get_macro_data(asset: str = None):
    if "macro" not in collectors:
        raise HTTPException(status_code=503, detail="Service not initialized")

    if asset:
        cached = await data_cache.get_macro_data(asset) if data_cache else None
        if cached:
            return cached

    await collectors["macro"].collect()
    result = {}

    data = collectors["macro"].get_latest_data(asset) if asset else collectors["macro"].get_latest_data()

    if isinstance(data, dict):
        for asset_name, macro_data in data.items():
            info = collectors["macro"].get_asset_info(asset_name)
            result[asset_name] = {
                "name": info.get("name", asset_name),
                "price": macro_data.price,
                "change_1d": macro_data.change_1d,
                "change_7d": macro_data.change_7d,
                "sources": macro_data.sources_used,
                "timestamp": macro_data.timestamp.isoformat()
            }

    if asset and data_cache:
        await data_cache.set_macro_data(asset, result)

    return result


@app.get("/api/v1/data/news")
async def get_news(
    limit: int = 20,
    sentiment: str = None,
    black_swan_only: bool = False
):
    if "news" not in collectors:
        raise HTTPException(status_code=503, detail="Service not initialized")

    if not black_swan_only and not sentiment:
        cached = await data_cache.get_news_list(sentiment, limit) if data_cache else None
        if cached:
            return {"news": cached, "source": "cache"}

    await collectors["news"].collect()

    if black_swan_only:
        news_list = collectors["news"].get_black_swan_news()
    elif sentiment:
        news_list = collectors["news"].get_news_by_sentiment(sentiment)
    else:
        news_list = collectors["news"].get_latest_news(limit=limit)

    if not black_swan_only and not sentiment and data_cache:
        await data_cache.set_news_list(news_list, sentiment, limit)

    return {"news": news_list, "count": len(news_list)}


@app.get("/api/v1/data/trader/sentiment")
async def get_trader_sentiment():
    if "trader" not in collectors:
        raise HTTPException(status_code=503, detail="Service not initialized")

    cached = await data_cache.get_trader_sentiment() if data_cache else None
    if cached:
        return cached

    await collectors["trader"].collect()
    sentiment = collectors["trader"].get_aggregate_sentiment()

    result = {
        "sentiment": sentiment["sentiment"],
        "score": sentiment["score"],
        "count": sentiment["count"],
        "bullish_count": sentiment["bullish_count"],
        "bearish_count": sentiment["bearish_count"]
    }

    if data_cache:
        await data_cache.set_trader_sentiment(result)

    return result


@app.get("/api/v1/data/trader/opinions")
async def get_trader_opinions(asset: str = None, sentiment: str = None):
    if "trader" not in collectors:
        raise HTTPException(status_code=503, detail="Service not initialized")

    await collectors["trader"].collect()

    if asset:
        opinions = collectors["trader"].get_opinions_by_asset(asset)
    elif sentiment == "bullish":
        opinions = collectors["trader"].get_bullish_traders()
    elif sentiment == "bearish":
        opinions = collectors["trader"].get_bearish_traders()
    else:
        opinions = [
            collectors["trader"].statement_to_dict(s)
            for s in collectors["trader"].latest_statements
        ]

    return {"opinions": opinions, "count": len(opinions)}


@app.get("/api/v1/data/crypto_stocks")
async def get_crypto_stocks():
    if "crypto_stock" not in collectors:
        raise HTTPException(status_code=503, detail="Service not initialized")

    cached = await data_cache.get_crypto_stocks() if data_cache else None
    if cached:
        return {"stocks": cached, "source": "cache"}

    await collectors["crypto_stock"].collect()
    stocks = collectors["crypto_stock"].get_all_stocks()

    result = [
        {
            "symbol": symbol,
            "name": stock.name,
            "price": stock.price,
            "change_1d": stock.change_1d,
            "change_7d": stock.change_7d,
            "volume": stock.volume,
            "source": stock.source
        }
        for symbol, stock in stocks.items()
    ]

    if data_cache:
        await data_cache.set_crypto_stocks(result)

    return {"stocks": result}


@app.get("/api/v1/data/social/{platform}")
async def get_social_posts(platform: str, limit: int = 20):
    if "social" not in collectors:
        raise HTTPException(status_code=503, detail="Service not initialized")

    cached = await data_cache.get_social_posts(platform, limit) if data_cache else None
    if cached:
        return {"posts": cached, "source": "cache"}

    await collectors["social"].collect()

    if platform in ["twitter", "reddit"]:
        posts = collectors["social"].get_posts_by_platform(platform)
        result = posts[:limit]

        if data_cache:
            await data_cache.set_social_posts(platform, result, limit)

        return {"posts": result, "count": len(result)}

    raise HTTPException(status_code=400, detail="Invalid platform")


@app.post("/api/v1/collector/{collector_name}/collect")
async def trigger_collect(collector_name: str):
    if collector_name not in collectors:
        raise HTTPException(status_code=404, detail="Collector not found")

    try:
        result = await collectors[collector_name].collect_with_resilience()
        if result.success:
            return {
                "status": "ok",
                "collector": collector_name,
                "message": "Collection triggered",
                "data": result.data,
                "confidence": result.confidence
            }
        else:
            return {
                "status": "degraded",
                "collector": collector_name,
                "message": f"Collection completed with fallback: {result.error}",
                "data": result.data,
                "confidence": result.confidence
            }
    except Exception as e:
        return {"status": "error", "collector": collector_name, "message": str(e)}


@app.get("/api/v1/collector/{collector_name}/status")
async def get_collector_status(collector_name: str):
    if collector_name not in collectors:
        raise HTTPException(status_code=404, detail="Collector not found")

    collector = collectors[collector_name]
    last_run = None
    items_count = 0

    if hasattr(collector, "last_collect_time"):
        last_run = collector.last_collect_time.isoformat() if collector.last_collect_time else None
    if hasattr(collector, "get_item_count"):
        items_count = collector.get_item_count()

    return {
        "collector": collector_name,
        "status": "running" if last_run else "pending",
        "last_run": last_run,
        "items_count": items_count
    }


@app.post("/api/v1/webhook/news")
async def webhook_news(
    payload: NewsWebhookPayload,
    x_webhook_signature: Optional[str] = Header(None)
):
    from infrastructure.webhook.receiver import get_webhook_receiver
    receiver = get_webhook_receiver()

    success = await receiver.receive(
        source=payload.source,
        event_type=payload.event_type,
        data=payload.data,
        signature=x_webhook_signature
    )

    if success:
        if data_cache:
            await data_cache.invalidate_news()
        return {"status": "ok", "message": "News processed"}
    return {"status": "error", "message": "Processing failed"}


@app.post("/api/v1/webhook/price")
async def webhook_price(payload: NewsWebhookPayload):
    from infrastructure.webhook.receiver import get_webhook_receiver
    receiver = get_webhook_receiver()

    success = await receiver.receive(
        source=payload.source,
        event_type=payload.event_type,
        data=payload.data
    )

    if success:
        symbol = payload.data.get("symbol")
        exchange = payload.data.get("exchange")
        if symbol and exchange and data_cache:
            await data_cache.invalidate_price(symbol, exchange)
        return {"status": "ok", "message": "Price processed"}
    return {"status": "error", "message": "Processing failed"}


@app.post("/api/v1/webhook/raw")
async def webhook_raw(request: Request):
    from infrastructure.webhook.receiver import get_webhook_receiver
    receiver = get_webhook_receiver()

    try:
        body = await request.body()
        json_data = await request.json()

        source = json_data.get("source", "custom")
        event_type = json_data.get("event_type", "unknown")
        data = json_data.get("data", {})

        signature = request.headers.get("x-webhook-signature")

        success = await receiver.receive(
            source=source,
            event_type=event_type,
            data=data,
            signature=signature,
            raw_body=body
        )

        return {"status": "ok" if success else "error"}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"status": "error", "message": str(e)}


@app.delete("/api/v1/cache/invalidate")
async def invalidate_cache(pattern: str = None):
    if not data_cache:
        raise HTTPException(status_code=503, detail="Cache not initialized")

    if pattern == "prices":
        for symbol in SYMBOLS:
            await data_cache.invalidate_price(symbol)
    elif pattern == "news":
        await data_cache.invalidate_news()
    elif pattern == "all":
        for symbol in SYMBOLS:
            await data_cache.invalidate_price(symbol)
        await data_cache.invalidate_news()
        await data_cache.invalidate_trader_sentiment()
        await data_cache.invalidate_crypto_stocks()
    else:
        raise HTTPException(status_code=400, detail="Invalid pattern")

    return {"status": "ok", "pattern": pattern}


@app.websocket("/ws/market")
async def websocket_market(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except Exception:
        pass
    finally:
        await ws_manager.disconnect(websocket)


async def run_data_collection():
    while True:
        try:
            if "exchange" in collectors:
                result = await collectors["exchange"].collect_with_resilience()
                if result.success and result.data:
                    prices = result.data
                    for symbol, multi_prices in prices.items():
                        for exchange, price in multi_prices.prices.items():
                            if price.status == "ok":
                                price_data = {
                                    "price": price.price,
                                    "bid": price.bid,
                                    "ask": price.ask,
                                    "spread": price.spread,
                                    "volume_24h": price.volume_24h,
                                    "high_24h": price.high_24h,
                                    "low_24h": price.low_24h,
                                    "change_24h": price.change_24h
                                }

                                if data_cache:
                                    await data_cache.set_price(symbol, exchange, price_data)

                                await data_storage.store_price(symbol, exchange, price_data)

                                if tdp_adapter:
                                    await tdp_adapter.publish_price(TDPPriceData(
                                        symbol=symbol,
                                        exchange=exchange,
                                        price=price.price,
                                        bid=price.bid,
                                        ask=price.ask,
                                        spread=price.spread,
                                        volume_24h=price.volume_24h,
                                        high_24h=price.high_24h,
                                        low_24h=price.low_24h,
                                        change_24h=price.change_24h,
                                        timestamp=datetime.now().timestamp()
                                    ))

                                await ws_manager.broadcast({
                                    "type": "price",
                                    "symbol": symbol,
                                    "exchange": exchange,
                                    "data": price_data
                                })
                else:
                    logger.warning(f"Exchange collection failed: {result.error}")

            if "etf" in collectors:
                result = await collectors["etf"].collect_with_resilience()
                if result.success and result.data:
                    etf_data = result.data
                    for symbol, flow in etf_data.items():
                        etf_dict = {
                            "net_flow": flow.net_flow,
                            "inflow": flow.inflow,
                            "outflow": flow.outflow,
                            "aum": flow.aum
                        }
                        if data_cache:
                            await data_cache.set_etf_flow(symbol, etf_dict)
                        await data_storage.store_etf_flow(symbol, etf_dict)

                        if tdp_adapter:
                            await tdp_adapter.publish_etf(TDPEtfData(
                                symbol=symbol,
                                net_flow=flow.net_flow,
                                inflow=flow.inflow,
                                outflow=flow.outflow,
                                aum=flow.aum,
                                sources=flow.sources_used,
                                timestamp=datetime.now().timestamp()
                            ))
                else:
                    logger.warning(f"ETF collection failed: {result.error}")

            if "macro" in collectors:
                await collectors["macro"].collect_with_resilience()

            if "crypto_stock" in collectors:
                await collectors["crypto_stock"].collect_with_resilience()

        except Exception as e:
            logger.error(f"Data collection error: {e}")

        await asyncio.sleep(CHECK_INTERVAL)


async def run_news_collection():
    while True:
        try:
            if "news" in collectors:
                result = await collectors["news"].collect_with_resilience()
                if result.success and result.data:
                    news_list = result.data
                    for news in news_list[:5]:
                        news_dict = {
                            "id": news.get("id", ""),
                            "title": news.get("title", ""),
                            "content": news.get("content", ""),
                            "url": news.get("url", ""),
                            "source": news.get("source", ""),
                            "published_at": news.get("published_at", 0),
                            "sentiment": news.get("sentiment", "neutral"),
                            "sentiment_score": news.get("sentiment_score", 0.0),
                            "entities": news.get("entities", []),
                            "topics": news.get("topics", []),
                            "black_swan": news.get("black_swan", False),
                        }

                        await data_storage.store_news(news_dict)

                        if tdp_adapter:
                            await tdp_adapter.publish_news(TDPNewsData(
                                id=news_dict["id"],
                                title=news_dict["title"],
                                content=news_dict["content"],
                                url=news_dict["url"],
                                source=news_dict["source"],
                                published_at=news_dict["published_at"],
                                sentiment=news_dict["sentiment"],
                                sentiment_score=news_dict["sentiment_score"],
                                entities=news_dict["entities"],
                                topics=news_dict["topics"],
                                black_swan=news_dict["black_swan"],
                                timestamp=datetime.now().timestamp()
                            ))

                        await ws_manager.broadcast({
                            "type": "news",
                            "data": news
                        })
                else:
                    logger.warning(f"News collection failed: {result.error}")

            if "trader" in collectors:
                result = await collectors["trader"].collect_with_resilience()
                if result.success and result.data:
                    trader_data = result.data.get("statements", [])
                    for opinion in trader_data:
                        opinion_dict = {
                            "trader": opinion.get("trader", ""),
                            "asset": opinion.get("asset", ""),
                            "opinion": opinion.get("opinion", ""),
                            "sentiment": opinion.get("sentiment", "neutral"),
                            "confidence": opinion.get("confidence", 0.0),
                            "posted_at": opinion.get("posted_at", 0),
                            "sources": opinion.get("sources", []),
                        }
                        await data_storage.store_trader_opinion(opinion_dict)

                        if tdp_adapter:
                            await tdp_adapter.publish_trader_opinion(TDPTraderOpinion(
                                trader=opinion_dict["trader"],
                                asset=opinion_dict["asset"],
                                opinion=opinion_dict["opinion"],
                                sentiment=opinion_dict["sentiment"],
                                confidence=opinion_dict["confidence"],
                                posted_at=opinion_dict["posted_at"],
                                sources=opinion_dict["sources"],
                                timestamp=datetime.now().timestamp()
                            ))
                else:
                    logger.warning(f"Trader collection failed: {result.error}")

            if "social" in collectors:
                await collectors["social"].collect_with_resilience()

        except Exception as e:
            logger.error(f"News collection error: {e}")

        await asyncio.sleep(NEWS_INTERVAL)


if __name__ == "__main__":
    import uvicorn
    host = API_GATEWAY_CONFIGS.get("api_gateway.host", "0.0.0.0")
    port = API_GATEWAY_CONFIGS.get("api_gateway.port", 8002)
    uvicorn.run(app, host=host, port=port)
