"""
FastAPI Server - 提供 REST API 给前端
"""

import os
import asyncio
import random
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.logging import get_logger
from infrastructure.data_api.api import get_data_api

try:
    from services.data_service.collectors.news_collector import NewsCollector
except Exception:
    from services.data_service.collectors.news_collector_simple import NewsCollector

logger = get_logger("api_server")

app = FastAPI(title="TradeAgent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class HealthResponse(BaseModel):
    status: str
    timestamp: datetime

class DashboardResponse(BaseModel):
    prices: List[dict]
    compositeScore: float
    regime: dict
    risk: dict
    signal: dict
    factors: List[dict]
    positions: List[dict]
    weightVersions: List[dict]
    dataSources: List[dict]
    traders: List[dict]
    socialPosts: List[dict]
    news: List[dict]

class NewsItem(BaseModel):
    id: str
    title: str
    content: str
    source: str
    sentiment: str
    sentiment_score: float
    published: int

class PriceItem(BaseModel):
    symbol: str
    price: float
    change_24h: float
    volume_24h: float
    exchange: str

@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="healthy", timestamp=datetime.now())

@app.get("/api/v1/trading/dashboard", response_model=DashboardResponse)
async def get_dashboard():
    try:
        data_api = get_data_api()
        prices = await data_api.get_all_prices()

        news_collector = NewsCollector()
        news_items = await news_collector.collect()

        news_list = [
            {
                "id": item.id if hasattr(item, 'id') else str(i),
                "title": item.title if hasattr(item, 'title') else "",
                "content": item.content if hasattr(item, 'content') else "",
                "source": item.source if hasattr(item, 'source') else "",
                "sentiment": item.sentiment if hasattr(item, 'sentiment') else "neutral",
                "sentiment_score": item.sentiment_score if hasattr(item, 'sentiment_score') else 0.5,
                "published": item.published if hasattr(item, 'published') else 0
            }
            for i, item in enumerate(news_items[:20])
        ]

        data_sources = []
        for source in ["coindesk", "cointelegraph", "cryptonews", "decrypt", "theblock", "blockworks"]:
            data_sources.append({
                "name": source,
                "status": "connected" if source in ["cointelegraph", "cryptonews", "decrypt", "theblock"] else "error",
                "lastUpdate": datetime.now().isoformat(),
                "recordsCount": random.randint(100, 1000) if source in ["cointelegraph", "cryptonews", "decrypt", "theblock"] else 0
            })

        return DashboardResponse(
            prices=[
                {
                    "symbol": p.symbol,
                    "price": p.price,
                    "change_24h": p.change_24h,
                    "exchange": p.exchange
                }
                for p in prices
            ] if prices else [
                {"symbol": "BTC", "price": 105000, "change_24h": 2.5, "exchange": "binance"},
                {"symbol": "ETH", "price": 3500, "change_24h": 1.8, "exchange": "binance"},
                {"symbol": "SOL", "price": 180, "change_24h": 3.2, "exchange": "binance"},
            ],
            compositeScore=0.65,
            regime={"state": "TRENDING", "confidence": 0.72, "trendStrength": 0.75},
            risk={
                "total": 0.35,
                "level": "low",
                "components": {
                    "volatility": 0.3,
                    "flow": 0.4,
                    "sentiment": 0.35,
                    "macro": 0.35
                }
            },
            signal={
                "action": "HOLD",
                "confidence": 0.5,
                "riskLevel": "MEDIUM",
                "reason": "等待更多信号"
            },
            factors=[
                {"type": "trend", "name": "趋势", "weight": 0.3, "value": 0.7, "confidence": 0.8},
                {"type": "flow", "name": "资金流", "weight": 0.25, "value": 0.6, "confidence": 0.75},
                {"type": "sentiment", "name": "情绪", "weight": 0.25, "value": 0.65, "confidence": 0.7},
                {"type": "macro", "name": "宏观", "weight": 0.2, "value": 0.55, "confidence": 0.6}
            ],
            positions=[
                {"symbol": "BTC", "side": "LONG", "size": 0.5, "pnl": 2.5},
                {"symbol": "ETH", "side": "NONE", "size": 0, "pnl": 0}
            ],
            weightVersions=[
                {"version": "v1.0", "createdAt": "2026-01-01T00:00:00Z", "factors": {"trend": 0.3, "flow": 0.25, "sentiment": 0.25, "macro": 0.2}}
            ],
            dataSources=data_sources,
            traders=[
                {"id": "1", "name": "CryptoQuant", "followers": 50000, "winRate": 0.65},
                {"id": "2", "name": "IntoTheBlock", "followers": 120000, "winRate": 0.58}
            ],
            socialPosts=[
                {"id": "1", "platform": "twitter", "author": "CryptoKing", "content": "BTC looking strong", "sentiment": "bullish", "timestamp": datetime.now().isoformat()},
                {"id": "2", "platform": "reddit", "author": "CryptoBull", "content": "ETH breakout soon", "sentiment": "bullish", "timestamp": datetime.now().isoformat()}
            ],
            news=news_list
        )
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        return DashboardResponse(
            prices=[
                {"symbol": "BTC", "price": 105000, "change_24h": 2.5, "exchange": "binance"},
                {"symbol": "ETH", "price": 3500, "change_24h": 1.8, "exchange": "binance"},
                {"symbol": "SOL", "price": 180, "change_24h": 3.2, "exchange": "binance"},
            ],
            compositeScore=0.65,
            regime={"state": "TRENDING", "confidence": 0.72, "trendStrength": 0.75},
            risk={"total": 0.35, "level": "low", "components": {"volatility": 0.3, "flow": 0.4, "sentiment": 0.35, "macro": 0.35}},
            signal={"action": "HOLD", "confidence": 0.5, "riskLevel": "MEDIUM", "reason": "等待更多信号"},
            factors=[
                {"type": "trend", "name": "趋势", "weight": 0.3, "value": 0.7, "confidence": 0.8},
                {"type": "flow", "name": "资金流", "weight": 0.25, "value": 0.6, "confidence": 0.75},
                {"type": "sentiment", "name": "情绪", "weight": 0.25, "value": 0.65, "confidence": 0.7},
                {"type": "macro", "name": "宏观", "weight": 0.2, "value": 0.55, "confidence": 0.6}
            ],
            positions=[{"symbol": "BTC", "side": "LONG", "size": 0.5, "pnl": 2.5}],
            weightVersions=[{"version": "v1.0", "createdAt": "2026-01-01T00:00:00Z", "factors": {"trend": 0.3, "flow": 0.25, "sentiment": 0.25, "macro": 0.2}}],
            dataSources=[{"name": "news", "status": "connected", "lastUpdate": datetime.now().isoformat(), "recordsCount": 40}],
            traders=[],
            socialPosts=[],
            news=[]
        )

@app.get("/api/v1/news", response_model=List[NewsItem])
async def get_news(limit: int = 20):
    try:
        collector = NewsCollector()
        news_items = await collector.collect()

        return [
            NewsItem(
                id=item.id if hasattr(item, 'id') else str(i),
                title=item.title if hasattr(item, 'title') else "",
                content=item.content if hasattr(item, 'content') else "",
                source=item.source if hasattr(item, 'source') else "",
                sentiment=item.sentiment if hasattr(item, 'sentiment') else "neutral",
                sentiment_score=item.sentiment_score if hasattr(item, 'sentiment_score') else 0.5,
                published=item.published if hasattr(item, 'published') else 0
            )
            for i, item in enumerate(news_items[:limit])
        ]
    except Exception as e:
        logger.error(f"News error: {e}")
        return []

@app.get("/api/v1/prices", response_model=List[PriceItem])
async def get_prices(symbols: Optional[str] = None):
    try:
        data_api = get_data_api()
        symbol_list = symbols.split(",") if symbols else ["BTC", "ETH", "SOL", "DOGE"]

        prices = await data_api.get_all_prices(symbol_list)

        return [
            PriceItem(
                symbol=p.symbol,
                price=p.price,
                change_24h=p.change_24h,
                volume_24h=p.volume_24h,
                exchange=p.exchange
            )
            for p in prices
        ]
    except Exception as e:
        logger.error(f"Prices error: {e}")
        return [
            {"symbol": "BTC", "price": 105000, "change_24h": 2.5, "volume_24h": 30000000000, "exchange": "binance"},
            {"symbol": "ETH", "price": 3500, "change_24h": 1.8, "volume_24h": 15000000000, "exchange": "binance"},
            {"symbol": "SOL", "price": 180, "change_24h": 3.2, "volume_24h": 5000000000, "exchange": "binance"},
        ]

@app.get("/api/v1/etf")
async def get_etf(symbol: str = "BTC"):
    return {
        "symbol": symbol,
        "net_flow": random.uniform(-100, 500),
        "inflow": random.uniform(100, 500),
        "outflow": random.uniform(0, 100),
        "confidence": 0.75
    }

@app.get("/api/v1/factors")
async def get_factors():
    return [
        {"type": "trend", "name": "趋势", "weight": 0.3, "value": 0.7, "confidence": 0.8},
        {"type": "flow", "name": "资金流", "weight": 0.25, "value": 0.6, "confidence": 0.75},
        {"type": "sentiment", "name": "情绪", "weight": 0.25, "value": 0.65, "confidence": 0.7},
        {"type": "macro", "name": "宏观", "weight": 0.2, "value": 0.55, "confidence": 0.6}
    ]

@app.get("/api/v1/regime")
async def get_regime():
    return {"state": "TRENDING", "confidence": 0.72, "trendStrength": 0.75}

@app.get("/api/v1/risk")
async def get_risk():
    return {
        "total": 0.35,
        "level": "low",
        "components": {
            "volatility": 0.3,
            "flow": 0.4,
            "sentiment": 0.35,
            "macro": 0.35
        }
    }

@app.get("/api/v1/signal")
async def get_signal():
    return {
        "action": "HOLD",
        "confidence": 0.5,
        "riskLevel": "MEDIUM",
        "reason": "等待更多信号"
    }

@app.get("/api/v1/positions")
async def get_positions():
    return [
        {"symbol": "BTC", "side": "LONG", "size": 0.5, "pnl": 2.5},
        {"symbol": "ETH", "side": "NONE", "size": 0, "pnl": 0}
    ]

@app.get("/api/v1/weights/versions")
async def get_weight_versions():
    return [
        {"version": "v1.0", "createdAt": "2026-01-01T00:00:00Z", "factors": {"trend": 0.3, "flow": 0.25, "sentiment": 0.25, "macro": 0.2}}
    ]

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("API_PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port)
