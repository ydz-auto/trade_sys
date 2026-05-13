"""
FastAPI Server - 提供 REST API 给前端
"""

import os
import asyncio
import random
import httpx
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
    """获取完整交易仪表板 - 离线模式"""
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
        news=[
            {
                "id": "1",
                "title": "比特币突破新高",
                "content": "比特币价格创下历史新高，市场情绪乐观",
                "source": "cointelegraph",
                "sentiment": "bullish",
                "sentiment_score": 0.85,
                "published": int(datetime.now().timestamp())
            },
            {
                "id": "2",
                "title": "以太坊升级即将到来",
                "content": "以太坊网络升级预计将在下周进行",
                "source": "cryptonews",
                "sentiment": "neutral",
                "sentiment_score": 0.5,
                "published": int(datetime.now().timestamp()) - 3600
            }
        ]
    )

@app.get("/api/v1/news", response_model=List[NewsItem])
async def get_news(limit: int = 20):
    """获取新闻列表 - 离线模式"""
    return [
        NewsItem(
            id=str(i),
            title=f"市场新闻 {i+1}",
            content=f"这是第 {i+1} 条新闻的内容",
            source="cointelegraph" if i % 2 == 0 else "cryptonews",
            sentiment="bullish" if i % 3 == 0 else "bearish" if i % 3 == 1 else "neutral",
            sentiment_score=random.uniform(0.3, 0.9),
            published=int(datetime.now().timestamp()) - i * 1800
        )
        for i in range(min(limit, 10))
    ]

@app.get("/api/v1/prices", response_model=List[PriceItem])
async def get_prices(symbols: Optional[str] = None):
    """获取价格数据 - 真实市场数据"""
    symbol_map = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "SOL": "solana",
        "DOGE": "dogecoin",
        "BNB": "binancecoin"
    }
    coin_ids = ",".join(symbol_map.get(s.upper(), s.lower()) for s in (symbols.split(",") if symbols else ["BTC", "ETH", "SOL", "DOGE"]))
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"https://api.coingecko.com/api/v3/simple/price",
                params={
                    "ids": coin_ids,
                    "vs_currencies": "usd",
                    "include_24hr_change": "true",
                    "include_24hr_vol": "true"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                symbol_reverse = {v: k for k, v in symbol_map.items()}
                
                prices = []
                for coin_id, values in data.items():
                    symbol = symbol_reverse.get(coin_id, coin_id.upper())
                    prices.append(PriceItem(
                        symbol=symbol,
                        price=values.get("usd", 0),
                        change_24h=values.get("usd_24h_change", 0),
                        volume_24h=values.get("usd_24h_vol", 0),
                        exchange="coingecko"
                    ))
                
                return prices
            else:
                raise Exception(f"CoinGecko API error: {response.status_code}")
                
    except Exception as e:
        logger.error(f"Price API error: {e}")
        
        price_map = {
            "BTC": {"price": 105000, "change": 2.5},
            "ETH": {"price": 3500, "change": 1.8},
            "SOL": {"price": 180, "change": 3.2},
            "DOGE": {"price": 0.25, "change": -1.2},
        }
        
        symbol_list = symbols.split(",") if symbols else ["BTC", "ETH", "SOL", "DOGE"]
        return [
            PriceItem(
                symbol=symbol.upper(),
                price=price_map.get(symbol.upper(), {"price": 100})["price"] * random.uniform(0.98, 1.02),
                change_24h=price_map.get(symbol.upper(), {"change": 0})["change"],
                volume_24h=random.uniform(1000000000, 50000000000),
                exchange="fallback"
            )
            for symbol in symbol_list
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
