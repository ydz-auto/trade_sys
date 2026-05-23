"""
Prices Service - Price Comparison Logic

从 Redis 读取真实数据，只有 mock 模式才返回假数据
"""

import os
import json
from datetime import datetime
from typing import Dict, Any, Optional
from ..schemas import PriceComparisonResponse, PriceSourceStatusResponse
from application.queries.infrastructure_queries import get_redis_client_sync
from domain.logging import get_logger

logger = get_logger("api.prices")


def _is_mock_mode() -> bool:
    """检查是否启用 mock 模式"""
    return os.getenv("DASHBOARD_MOCK", "false").lower() == "true"


async def _get_price_from_redis(symbol: str, exchange: str) -> Optional[Dict[str, Any]]:
    """从 Redis 获取价格数据"""
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


async def get_price_comparison(symbol: str) -> PriceComparisonResponse:
    """获取价格对比数据"""
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


async def get_price_source_status() -> PriceSourceStatusResponse:
    """获取价格源状态"""
    if _is_mock_mode():
        return PriceSourceStatusResponse(
            sources={
                "Binance": {"status": "online", "lastUpdate": datetime.now().isoformat(), "latency": 45},
                "OKX": {"status": "online", "lastUpdate": datetime.now().isoformat(), "latency": 38},
                "Bybit": {"status": "online", "lastUpdate": datetime.now().isoformat(), "latency": 52}
            }
        )
    
    redis = get_redis_client()
    sources = {}
    
    if redis:
        try:
            status_data = await redis.get("price_sources:status")
            if status_data:
                if isinstance(status_data, str):
                    status_data = json.loads(status_data)
                sources = status_data
        except Exception as e:
            logger.error(f"Error getting price source status from Redis: {e}")
    
    if not sources:
        exchanges = ["binance", "okx", "bybit", "coingecko"]
        for exchange in exchanges:
            price_data = await _get_price_from_redis("BTC", exchange)
            sources[exchange.capitalize()] = {
                "status": "online" if price_data else "offline",
                "lastUpdate": datetime.now().isoformat(),
                "latency": 0
            }
    
    return PriceSourceStatusResponse(sources=sources)
