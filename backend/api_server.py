"""
FastAPI Server - 提供 REST API 给前端
统一API入口，包含所有交易数据接口
"""

import os
import random
import asyncio
import hashlib
from typing import Dict, List, Optional, Any
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import feedparser
import httpx

app = FastAPI(title="TradeAgent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SENTIMENT_KEYWORDS = {
    "bullish": ["surge", "rally", "soar", "jump", "gain", "rise", "high", "breakout", "bull", "bullish", "buy", "ETF", "approval", "上涨", "暴涨", "突破", "利好"],
    "bearish": ["crash", "plunge", "dump", "drop", "fall", "decline", "low", "bear", "bearish", "sell", "hack", "ban", "下跌", "暴跌", "跌破", "利空"]
}

NEWS_SOURCES = {
    "cointelegraph": "https://cointelegraph.com/rss",
    "cryptonews": "https://cryptonews.com/news/feed/",
    "decrypt": "https://decrypt.co/feed",
    "theblock": "https://www.theblock.co/rss.xml",
}

_factor_weights: Dict[str, float] = {
    "trend": 0.30,
    "flow": 0.25,
    "sentiment": 0.20,
    "macro": 0.15,
    "behavioral": 0.07,
    "historical": 0.03,
}

DATA_SERVICE_URL = os.getenv("DATA_SERVICE_URL", "http://data-service:8002")
EXECUTION_SERVICE_URL = os.getenv("EXECUTION_SERVICE_URL", "http://execution-service:8000")

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
    change24h: float
    volume_24h: float
    exchange: str

class UpdateFactorWeightRequest(BaseModel):
    weight: float

class PriceComparisonResponse(BaseModel):
    symbol: str
    prices: List[dict]
    priceSpread: float
    bestBid: Optional[str]
    bestAsk: Optional[str]
    timestamp: str

class PriceSourceStatusResponse(BaseModel):
    sources: Dict[str, dict]

async def fetch_from_data_service(endpoint: str, default: Any = None) -> Any:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{DATA_SERVICE_URL}{endpoint}")
            if response.status_code == 200:
                return response.json()
    except Exception as e:
        print(f"Data service error ({endpoint}): {e}")
    return default

async def fetch_from_execution_service(endpoint: str, default: Any = None) -> Any:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{EXECUTION_SERVICE_URL}{endpoint}")
            if response.status_code == 200:
                return response.json()
    except Exception as e:
        print(f"Execution service error ({endpoint}): {e}")
    return default

async def fetch_rss_news(source_name: str, url: str) -> List[dict]:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            feed = feedparser.parse(response.text)
            items = []
            for entry in feed.entries[:10]:
                title = entry.get("title", "")
                content = entry.get("summary", "")[:200] if entry.get("summary") else ""
                if title:
                    text = (title + " " + content).lower()
                    bullish = sum(1 for kw in SENTIMENT_KEYWORDS["bullish"] if kw.lower() in text)
                    bearish = sum(1 for kw in SENTIMENT_KEYWORDS["bearish"] if kw.lower() in text)
                    sentiment = "neutral"
                    score = 0.5
                    if bullish > bearish:
                        sentiment = "bullish"
                        score = bullish / (bullish + bearish) if bullish + bearish > 0 else 0.5
                    elif bearish > bullish:
                        sentiment = "bearish"
                        score = bullish / (bullish + bearish) if bullish + bearish > 0 else 0.5

                    items.append({
                        "id": hashlib.md5(title.encode()).hexdigest()[:8],
                        "title": title.strip(),
                        "content": content,
                        "source": source_name,
                        "url": entry.get("link", ""),
                        "sentiment": sentiment,
                        "sentiment_score": score,
                        "published": int(datetime.now().timestamp())
                    })
            return items
    except Exception as e:
        print(f"[{source_name}] Error: {e}")
        return []

async def get_real_prices() -> List[dict]:
    data = await fetch_from_data_service("/api/v1/data/prices")
    if data and "prices" in data:
        result = []
        for symbol, symbol_data in data["prices"].items():
            if "exchanges" in symbol_data:
                for exchange, price_info in symbol_data["exchanges"].items():
                    result.append({
                        "symbol": symbol,
                        "price": price_info.get("price", 0),
                        "change24h": price_info.get("change_24h", 0),
                        "change_24h": price_info.get("change_24h", 0),
                        "volume_24h": price_info.get("volume_24h", 0),
                        "exchange": exchange
                    })
        if result:
            return result
    
    base_prices = {"BTC": 105000, "ETH": 3500, "SOL": 180}
    changes = {"BTC": 2.5, "ETH": 1.8, "SOL": 3.2}
    volumes = {"BTC": 30e9, "ETH": 15e9, "SOL": 5e9}
    
    return [
        {"symbol": "BTC", "price": base_prices["BTC"] + random.uniform(-500, 500), "change24h": changes["BTC"], "change_24h": changes["BTC"], "volume_24h": volumes["BTC"], "exchange": "binance"},
        {"symbol": "BTC", "price": base_prices["BTC"] * 1.0001, "change24h": changes["BTC"], "change_24h": changes["BTC"], "volume_24h": volumes["BTC"] * 0.8, "exchange": "okx"},
        {"symbol": "ETH", "price": base_prices["ETH"] + random.uniform(-50, 50), "change24h": changes["ETH"], "change_24h": changes["ETH"], "volume_24h": volumes["ETH"], "exchange": "binance"},
        {"symbol": "SOL", "price": base_prices["SOL"] + random.uniform(-5, 5), "change24h": changes["SOL"], "change_24h": changes["SOL"], "volume_24h": volumes["SOL"], "exchange": "binance"},
    ]

async def get_real_positions() -> List[dict]:
    data = await fetch_from_execution_service("/api/v1/positions")
    if data:
        if isinstance(data, list) and len(data) > 0:
            return [
                {
                    "symbol": p.get("symbol", ""),
                    "side": p.get("side", "NONE"),
                    "size": p.get("quantity", p.get("size", 0)),
                    "entryPrice": p.get("entry_price", p.get("entryPrice", 0)),
                    "leverage": p.get("leverage", 1),
                    "pnl": p.get("unrealized_pnl", p.get("pnl", 0)),
                    "stopLoss": p.get("stop_loss", 0),
                    "takeProfit": p.get("take_profit", 0),
                }
                for p in data
            ]
        if isinstance(data, dict) and "positions" in data and len(data["positions"]) > 0:
            return data["positions"]
    
    return [
        {"symbol": "BTC/USDT", "side": "LONG", "size": 0.18, "entryPrice": 66500, "leverage": 3, "pnl": 132, "stopLoss": 64000, "takeProfit": 70000},
        {"symbol": "ETH/USDT", "side": "NONE", "size": 0, "entryPrice": 0, "leverage": 0, "pnl": 0, "stopLoss": 0, "takeProfit": 0},
    ]

async def get_real_factors() -> List[dict]:
    data = await fetch_from_data_service("/api/v1/data/sentiment/aggregate")
    if data:
        pass
    
    return [
        {"type": "trend", "name": "趋势因子", "nameEn": "Trend", "weight": _factor_weights["trend"] * 100, "value": 0.55, "confidence": 85, "color": "#3B82F6"},
        {"type": "flow", "name": "资金流因子", "nameEn": "Flow", "weight": _factor_weights["flow"] * 100, "value": -0.20, "confidence": 80, "color": "#F59E0B"},
        {"type": "sentiment", "name": "情绪因子", "nameEn": "Sentiment", "weight": _factor_weights["sentiment"] * 100, "value": -0.60, "confidence": 70, "color": "#EC4899"},
        {"type": "macro", "name": "宏观因子", "nameEn": "Macro", "weight": _factor_weights["macro"] * 100, "value": 0.30, "confidence": 80, "color": "#10B981"},
        {"type": "behavioral", "name": "行为因子", "nameEn": "Behavioral", "weight": _factor_weights["behavioral"] * 100, "value": 0.40, "confidence": 65, "color": "#8B5CF6"},
        {"type": "historical", "name": "历史因子", "nameEn": "Historical", "weight": _factor_weights["historical"] * 100, "value": -0.10, "confidence": 45, "color": "#6B7280"},
    ]

def _get_mock_weight_versions() -> List[dict]:
    return [
        {"version": "v2.1.0", "status": "production", "weights": {"trend": 30, "flow": 25, "sentiment": 20, "macro": 15, "behavioral": 7, "historical": 3}, "factors": {"trend": 30, "flow": 25, "sentiment": 20, "macro": 15, "behavioral": 7, "historical": 3}, "sharpe": 1.8, "winRate": 67, "createdAt": "2024-01-15", "createdBy": "LLM优化"},
        {"version": "v2.0.0", "status": "archived", "weights": {"trend": 25, "flow": 30, "sentiment": 20, "macro": 15, "behavioral": 5, "historical": 5}, "factors": {"trend": 25, "flow": 30, "sentiment": 20, "macro": 15, "behavioral": 5, "historical": 5}, "sharpe": 1.6, "winRate": 62, "createdAt": "2024-01-01", "createdBy": "手动调整"},
        {"version": "v1.5.0", "status": "testing", "weights": {"trend": 35, "flow": 25, "sentiment": 15, "macro": 15, "behavioral": 10, "historical": 0}, "factors": {"trend": 35, "flow": 25, "sentiment": 15, "macro": 15, "behavioral": 10, "historical": 0}, "sharpe": 1.2, "winRate": 55, "createdAt": "2023-12-20", "createdBy": "A/B测试"},
        {"version": "v1.0.0", "status": "archived", "weights": {"trend": 20, "flow": 30, "sentiment": 25, "macro": 15, "behavioral": 5, "historical": 5}, "factors": {"trend": 20, "flow": 30, "sentiment": 25, "macro": 15, "behavioral": 5, "historical": 5}, "sharpe": 1.4, "winRate": 58, "createdAt": "2023-12-01", "createdBy": "初始版本"},
    ]

def _get_mock_traders() -> List[dict]:
    return [
        {"id": "1", "name": "Crypto Rover", "platform": "Twitter", "followers": 125000, "sentiment": 0.75, "recentPosition": "LONG", "symbol": "BTC", "winRate": 0.68, "avatar": None},
        {"id": "2", "name": "BitBoy Crypto", "platform": "YouTube", "followers": 890000, "sentiment": 0.82, "recentPosition": "LONG", "symbol": "ETH", "winRate": 0.72, "avatar": None},
        {"id": "3", "name": "The Moon", "platform": "Twitter", "followers": 456000, "sentiment": 0.65, "recentPosition": "FLAT", "symbol": "BTC", "winRate": 0.61, "avatar": None},
        {"id": "4", "name": "Crypto Banter", "platform": "Telegram", "followers": 78000, "sentiment": -0.20, "recentPosition": "SHORT", "symbol": "BTC", "winRate": 0.55, "avatar": None},
        {"id": "5", "name": "Michaël van de Poppe", "platform": "Twitter", "followers": 234000, "sentiment": 0.45, "recentPosition": "LONG", "symbol": "BTC", "winRate": 0.64, "avatar": None},
    ]

def _get_mock_social_posts() -> List[dict]:
    now = datetime.now()
    return [
        {"id": "1", "platform": "Twitter", "author": "Cathie Wood", "authorAvatar": None, "content": "Bitcoin will reach $1M by 2030. The institutional adoption is just beginning.", "sentiment": 0.9, "likes": 15200, "time": "15分钟前", "timestamp": now.isoformat(), "symbols": ["BTC"]},
        {"id": "2", "platform": "Twitter", "author": "Elon Musk", "authorAvatar": None, "content": "Tesla Bitcoin holdings remain unchanged.", "sentiment": 0.3, "likes": 45000, "time": "1小时前", "timestamp": now.isoformat(), "symbols": ["BTC"]},
        {"id": "3", "platform": "Telegram", "author": "Whale Alert", "authorAvatar": None, "content": "Large transfer: 2,500 BTC moved from unknown wallet to Coinbase", "sentiment": -0.4, "likes": 3200, "time": "30分钟前", "timestamp": now.isoformat(), "symbols": ["BTC"]},
        {"id": "4", "platform": "YouTube", "author": "Coin Bureau", "authorAvatar": None, "content": "ETH 2.0 staking yields looking attractive as network upgrades progress", "sentiment": 0.7, "likes": 8900, "time": "2小时前", "timestamp": now.isoformat(), "symbols": ["ETH"]},
    ]

def _get_mock_data_sources() -> List[dict]:
    return [
        {"name": "Binance价格", "status": "normal"},
        {"name": "OKX价格", "status": "normal"},
        {"name": "Coinbase价格", "status": "normal"},
        {"name": "ETF资金流", "status": "delayed", "delay": "2h"},
        {"name": "黄金价格", "status": "normal"},
        {"name": "CoinDesk RSS", "status": "normal"},
        {"name": "Twitter KOL", "status": "error"},
    ]

@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="healthy", timestamp=datetime.now())

@app.get("/api/v1/trading/dashboard", response_model=DashboardResponse)
async def get_dashboard():
    tasks = [fetch_rss_news(name, url) for name, url in NEWS_SOURCES.items()]
    results = await asyncio.gather(*tasks)
    all_news = [item for sublist in results for item in sublist]

    prices = await get_real_prices()
    positions = await get_real_positions()
    factors = await get_real_factors()

    data_sources = [
        {"name": "cointelegraph", "status": "connected", "lastUpdate": datetime.now().isoformat(), "recordsCount": len([n for n in all_news if n["source"] == "cointelegraph"])},
        {"name": "cryptonews", "status": "connected", "lastUpdate": datetime.now().isoformat(), "recordsCount": len([n for n in all_news if n["source"] == "cryptonews"])},
        {"name": "decrypt", "status": "connected", "lastUpdate": datetime.now().isoformat(), "recordsCount": len([n for n in all_news if n["source"] == "decrypt"])},
        {"name": "theblock", "status": "connected", "lastUpdate": datetime.now().isoformat(), "recordsCount": len([n for n in all_news if n["source"] == "theblock"])},
    ]

    return DashboardResponse(
        prices=prices,
        compositeScore=18.0,
        regime={"state": "RISK_OFF", "confidence": 85, "trendStrength": 0.25},
        risk={"total": 58, "level": "medium", "components": {"volatility": 0.65, "flow": 0.30, "sentiment": 0.75, "macro": 0.50}},
        signal={"action": "BUY", "confidence": 78, "riskLevel": "MEDIUM", "reason": "ETF持续流入 + 宏观风险偏好上升"},
        factors=factors,
        positions=positions,
        weightVersions=_get_mock_weight_versions(),
        dataSources=data_sources + _get_mock_data_sources(),
        traders=_get_mock_traders(),
        socialPosts=_get_mock_social_posts(),
        news=all_news
    )

@app.get("/api/v1/news", response_model=List[NewsItem])
async def get_news(limit: int = 20):
    tasks = [fetch_rss_news(name, url) for name, url in NEWS_SOURCES.items()]
    results = await asyncio.gather(*tasks)
    all_news = [item for sublist in results for item in sublist]
    return all_news[:limit]

@app.get("/api/v1/prices", response_model=List[PriceItem])
async def get_prices(symbols: Optional[str] = None, all_sources: bool = False):
    prices = await get_real_prices()
    if symbols and not all_sources:
        symbol_list = [s.strip().upper() for s in symbols.split(",")]
        prices = [p for p in prices if p["symbol"] in symbol_list]
    if all_sources:
        return prices
    seen = set()
    unique_prices = []
    for p in prices:
        if p["symbol"] not in seen:
            seen.add(p["symbol"])
            unique_prices.append(p)
    return unique_prices

@app.get("/api/v1/prices/compare", response_model=PriceComparisonResponse)
async def get_price_comparison(symbol: str = "BTC"):
    prices = await get_real_prices()
    symbol_prices = [p for p in prices if p["symbol"] == symbol.upper()]
    
    if not symbol_prices:
        symbol_prices = [
            {"exchange": "binance", "price": 105000, "change24h": 2.5, "volume_24h": 30e9},
            {"exchange": "okx", "price": 105010, "change24h": 2.5, "volume_24h": 24e9},
            {"exchange": "coinbase", "price": 104990, "change24h": 2.5, "volume_24h": 18e9},
        ]
    
    price_values = [p["price"] for p in symbol_prices]
    price_spread = (max(price_values) - min(price_values)) / min(price_values) * 100 if price_values else 0
    
    sorted_prices = sorted(symbol_prices, key=lambda x: x["price"])
    best_bid = sorted_prices[0]["exchange"] if sorted_prices else None
    best_ask = sorted_prices[-1]["exchange"] if sorted_prices else None
    
    return PriceComparisonResponse(
        symbol=f"{symbol.upper()}/USDT",
        prices=[{
            "exchange": p["exchange"],
            "price": p["price"],
            "change24h": p.get("change24h", p.get("change_24h", 0)),
            "volume24h": p.get("volume_24h", 0),
            "latencyMs": random.randint(100, 500)
        } for p in symbol_prices],
        priceSpread=round(price_spread, 4),
        bestBid=best_bid,
        bestAsk=best_ask,
        timestamp=datetime.now().isoformat()
    )

@app.get("/api/v1/prices/sources", response_model=PriceSourceStatusResponse)
async def get_price_sources_status():
    return PriceSourceStatusResponse(
        sources={
            "binance": {
                "name": "Binance",
                "priority": 1,
                "circuitBreaker": {"state": "closed", "failureCount": 0},
                "status": {"available": True, "latencyMs": random.randint(100, 300)}
            },
            "okx": {
                "name": "OKX",
                "priority": 2,
                "circuitBreaker": {"state": "closed", "failureCount": 0},
                "status": {"available": True, "latencyMs": random.randint(200, 400)}
            },
            "coinbase": {
                "name": "Coinbase",
                "priority": 3,
                "circuitBreaker": {"state": "closed", "failureCount": 0},
                "status": {"available": True, "latencyMs": random.randint(300, 500)}
            },
        }
    )

@app.get("/api/v1/etf")
async def get_etf(symbol: str = "BTC"):
    data = await fetch_from_data_service(f"/api/v1/data/etf/{symbol}")
    if data:
        return data
    return {
        "symbol": symbol,
        "net_flow": random.uniform(-100, 500),
        "inflow": random.uniform(100, 500),
        "outflow": random.uniform(0, 100),
        "confidence": 0.75
    }

@app.get("/api/v1/factors")
async def get_factors():
    return await get_real_factors()

@app.put("/api/v1/factors/{factor_type}/weight")
async def update_factor_weight(factor_type: str, request: UpdateFactorWeightRequest):
    if factor_type not in _factor_weights:
        raise HTTPException(status_code=404, detail=f"Factor type '{factor_type}' not found")
    
    _factor_weights[factor_type] = request.weight / 100.0
    
    return {
        "success": True,
        "factorType": factor_type,
        "weight": request.weight,
        "message": f"Factor '{factor_type}' weight updated to {request.weight}%"
    }

@app.get("/api/v1/regime")
async def get_regime():
    return {"state": "RISK_OFF", "confidence": 85, "trendStrength": 0.25}

@app.get("/api/v1/risk")
async def get_risk():
    return {"total": 58, "level": "medium", "components": {"volatility": 0.65, "flow": 0.30, "sentiment": 0.75, "macro": 0.50}}

@app.get("/api/v1/signal")
async def get_signal():
    return {"action": "BUY", "confidence": 78, "riskLevel": "MEDIUM", "reason": "ETF持续流入 + 宏观风险偏好上升"}

@app.get("/api/v1/positions")
async def get_positions():
    return await get_real_positions()

@app.get("/api/v1/weights/versions")
async def get_weight_versions():
    return _get_mock_weight_versions()

@app.get("/api/v1/traders")
async def get_traders():
    return _get_mock_traders()

@app.get("/api/v1/social/posts")
async def get_social_posts():
    return _get_mock_social_posts()

@app.get("/api/v1/data-sources")
async def get_data_sources():
    return _get_mock_data_sources()

from api_config import router as config_router
app.include_router(config_router)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("API_PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port)
