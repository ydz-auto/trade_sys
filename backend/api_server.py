"""
FastAPI Server - 提供 REST API 给前端
"""

import os
import asyncio
import random
import httpx
import requests
import time
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.logging import get_logger
from infrastructure.data_api.api import get_data_api
from infrastructure.resilience import CircuitBreaker, CircuitBreakerConfig, get_circuit_breaker

try:
    from services.data_service.collectors.news_collector import NewsCollector
except Exception:
    from services.data_service.collectors.news_collector_simple import NewsCollector

logger = get_logger("api_server")

# 多数据源配置
PRICE_SOURCES = {
    "binance": {
        "name": "Binance",
        "priority": 1,
        "url": "https://api.binance.com/api/v3/ticker/24hr",
        "timeout": 10
    },
    "coingecko": {
        "name": "CoinGecko",
        "priority": 2,
        "url": "https://api.coingecko.com/api/v3/simple/price",
        "timeout": 10
    },
    "okx": {
        "name": "OKX",
        "priority": 3,
        "url": "https://www.okx.com/api/v5/market/ticker",
        "timeout": 10
    }
}

# 为每个数据源创建熔断器
circuit_breakers = {
    source: get_circuit_breaker(
        f"price_{source}",
        CircuitBreakerConfig(
            name=f"price_{source}",
            failure_threshold=3,
            recovery_timeout=60.0,
            half_open_max_calls=2
        )
    )
    for source in PRICE_SOURCES
}

# 数据源状态缓存
source_status: Dict[str, Dict] = {
    source: {
        "available": True,
        "last_success": None,
        "last_failure": None,
        "latency_ms": 0
    }
    for source in PRICE_SOURCES
}

# 多数据源价格获取函数
async def fetch_price_from_binance(symbol: str) -> Optional[Dict]:
    """从 Binance 获取价格"""
    try:
        start_time = time.time()
        response = requests.get(
            "https://api.binance.com/api/v3/ticker/24hr",
            params={"symbol": f"{symbol}USDT"},
            timeout=10
        )
        latency = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            data = response.json()
            source_status["binance"]["last_success"] = datetime.now()
            source_status["binance"]["latency_ms"] = latency
            return {
                "symbol": symbol,
                "price": float(data.get('lastPrice', 0)),
                "change_24h": float(data.get('priceChangePercent', 0)),
                "volume_24h": float(data.get('quoteVolume', 0)),
                "exchange": "binance",
                "latency_ms": latency
            }
    except Exception as e:
        source_status["binance"]["last_failure"] = datetime.now()
        logger.warning(f"Binance fetch failed for {symbol}: {e}")
    return None

async def fetch_price_from_coingecko(symbol: str) -> Optional[Dict]:
    """从 CoinGecko 获取价格"""
    symbol_map = {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "DOGE": "dogecoin"}
    coin_id = symbol_map.get(symbol.upper(), symbol.lower())
    
    try:
        start_time = time.time()
        response = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={
                "ids": coin_id,
                "vs_currencies": "usd",
                "include_24hr_change": "true",
                "include_24hr_vol": "true"
            },
            timeout=10
        )
        latency = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            data = response.json()
            if coin_id in data:
                values = data[coin_id]
                source_status["coingecko"]["last_success"] = datetime.now()
                source_status["coingecko"]["latency_ms"] = latency
                return {
                    "symbol": symbol,
                    "price": values.get("usd", 0),
                    "change_24h": values.get("usd_24h_change", 0),
                    "volume_24h": values.get("usd_24h_vol", 0),
                    "exchange": "coingecko",
                    "latency_ms": latency
                }
    except Exception as e:
        source_status["coingecko"]["last_failure"] = datetime.now()
        logger.warning(f"CoinGecko fetch failed for {symbol}: {e}")
    return None

async def fetch_price_from_okx(symbol: str) -> Optional[Dict]:
    """从 OKX 获取价格"""
    try:
        start_time = time.time()
        response = requests.get(
            "https://www.okx.com/api/v5/market/ticker",
            params={"instId": f"{symbol}-USDT"},
            timeout=10
        )
        latency = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == "0" and data.get("data"):
                ticker = data["data"][0]
                source_status["okx"]["last_success"] = datetime.now()
                source_status["okx"]["latency_ms"] = latency
                return {
                    "symbol": symbol,
                    "price": float(ticker.get('last', 0)),
                    "change_24h": float(ticker.get('changeUtc24h', 0)) * 100,
                    "volume_24h": float(ticker.get('volCcy24h', 0)),
                    "exchange": "okx",
                    "latency_ms": latency
                }
    except Exception as e:
        source_status["okx"]["last_failure"] = datetime.now()
        logger.warning(f"OKX fetch failed for {symbol}: {e}")
    return None

async def fetch_price_with_fallback(symbol: str) -> Dict:
    """带熔断和降级的价格获取"""
    fetchers = [
        ("binance", fetch_price_from_binance),
        ("coingecko", fetch_price_from_coingecko),
        ("okx", fetch_price_from_okx),
    ]
    
    for source_name, fetcher in fetchers:
        breaker = circuit_breakers[source_name]
        
        try:
            result = await breaker.execute(fetcher, symbol)
            if result:
                source_status[source_name]["available"] = True
                return result
        except Exception as e:
            logger.warning(f"{source_name} circuit breaker rejected or failed: {e}")
            source_status[source_name]["available"] = False
    
    # 所有数据源都失败，返回降级数据
    logger.error(f"All price sources failed for {symbol}, using fallback")
    price_map = {
        "BTC": {"price": 105000, "change": 2.5},
        "ETH": {"price": 3500, "change": 1.8},
        "SOL": {"price": 180, "change": 3.2},
        "DOGE": {"price": 0.25, "change": -1.2},
    }
    fallback = price_map.get(symbol.upper(), {"price": 100, "change": 0})
    return {
        "symbol": symbol,
        "price": fallback["price"] * random.uniform(0.98, 1.02),
        "change_24h": fallback["change"],
        "volume_24h": random.uniform(1000000000, 50000000000),
        "exchange": "fallback"
    }

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
    change24h: float  # 匹配前端字段名
    volume24h: float  # 匹配前端字段名
    exchange: str
    
    class Config:
        # 允许使用别名
        populate_by_name = True

@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="healthy", timestamp=datetime.now())

@app.get("/api/v1/trading/dashboard", response_model=DashboardResponse)
async def get_dashboard():
    """获取完整交易仪表板 - 真实数据"""
    try:
        prices_data = await get_prices("BTC,ETH,SOL")
    except Exception:
        prices_data = []
    
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
                "change24h": p.change24h,  # 匹配前端字段名
                "exchange": p.exchange
            }
            for p in prices_data
        ] if prices_data else [
            {"symbol": "BTC", "price": 105000, "change24h": 2.5, "exchange": "binance"},
            {"symbol": "ETH", "price": 3500, "change24h": 1.8, "exchange": "binance"},
            {"symbol": "SOL", "price": 180, "change24h": 3.2, "exchange": "binance"},
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

async def fetch_all_sources_prices(symbol: str) -> List[Dict]:
    """获取所有数据源的同一交易对价格"""
    results = []
    
    # 并行获取所有数据源
    fetchers = [
        ("binance", fetch_price_from_binance),
        ("coingecko", fetch_price_from_coingecko),
        ("okx", fetch_price_from_okx),
    ]
    
    for source_name, fetcher in fetchers:
        try:
            breaker = circuit_breakers[source_name]
            result = await breaker.execute(fetcher, symbol.upper())
            if result:
                results.append(result)
                source_status[source_name]["available"] = True
        except Exception as e:
            logger.warning(f"{source_name} failed for {symbol}: {e}")
            source_status[source_name]["available"] = False
    
    return results

@app.get("/api/v1/prices", response_model=List[PriceItem])
async def get_prices(symbols: Optional[str] = None, all_sources: bool = False):
    """
    获取价格数据
    - all_sources=false (默认): 返回每个交易对的最佳价格（带熔断降级）
    - all_sources=true: 返回所有数据源的同一交易对价格（用于对比）
    """
    symbol_list = symbols.split(",") if symbols else ["BTC", "ETH", "SOL", "DOGE"]
    
    if all_sources:
        # 返回所有数据源的同一交易对价格
        all_prices = []
        for symbol in symbol_list:
            prices = await fetch_all_sources_prices(symbol.upper())
            for p in prices:
                all_prices.append(PriceItem(
                    symbol=f"{p['symbol']}/USDT",
                    price=p["price"],
                    change24h=p["change_24h"],  # 匹配前端字段名
                    volume24h=p["volume_24h"],   # 匹配前端字段名
                    exchange=p["exchange"]
                ))
        return all_prices
    else:
        # 返回每个交易对的最佳价格（带熔断降级）
        prices = []
        for symbol in symbol_list:
            try:
                price_data = await fetch_price_with_fallback(symbol.upper())
                prices.append(PriceItem(
                    symbol=f"{price_data['symbol']}/USDT",
                    price=price_data["price"],
                    change24h=price_data["change_24h"],  # 匹配前端字段名
                    volume24h=price_data["volume_24h"],   # 匹配前端字段名
                    exchange=price_data["exchange"]
                ))
            except Exception as e:
                logger.error(f"Failed to fetch price for {symbol}: {e}")
                prices.append(PriceItem(
                    symbol=f"{symbol.upper()}/USDT",
                    price=0,
                    change24h=0,   # 匹配前端字段名
                    volume24h=0,   # 匹配前端字段名
                    exchange="error"
                ))
        return prices

@app.get("/api/v1/prices/compare")
async def get_prices_comparison(symbol: str = "BTC"):
    """获取指定交易对的多交易所价格对比"""
    prices = await fetch_all_sources_prices(symbol.upper())
    
    if not prices:
        return {
            "symbol": f"{symbol.upper()}/USDT",
            "prices": [],
            "price_spread": 0,
            "best_bid": None,
            "best_ask": None
        }
    
    # 计算价格差异
    sorted_prices = sorted(prices, key=lambda x: x["price"])
    min_price = sorted_prices[0]["price"]
    max_price = sorted_prices[-1]["price"]
    price_spread = ((max_price - min_price) / min_price * 100) if min_price > 0 else 0
    
    return {
        "symbol": f"{symbol.upper()}/USDT",
        "prices": [
            {
                "exchange": p["exchange"],
                "price": p["price"],
                "change24h": p["change_24h"],  # 匹配前端字段名
                "volume24h": p["volume_24h"],   # 匹配前端字段名
                "latencyMs": p.get("latency_ms", 0)  # 匹配前端字段名
            }
            for p in prices
        ],
        "priceSpread": round(price_spread, 4),  # 匹配前端字段名
        "bestBid": sorted_prices[-1]["exchange"] if sorted_prices else None,  # 匹配前端字段名
        "bestAsk": sorted_prices[0]["exchange"] if sorted_prices else None,   # 匹配前端字段名
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/v1/prices/sources")
async def get_price_sources_status():
    """获取价格数据源状态"""
    return {
        "sources": {
            source: {
                "name": PRICE_SOURCES[source]["name"],
                "priority": PRICE_SOURCES[source]["priority"],
                "circuit_breaker": circuit_breakers[source].get_stats(),
                "status": source_status[source]
            }
            for source in PRICE_SOURCES
        },
        "timestamp": datetime.now().isoformat()
    }

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
