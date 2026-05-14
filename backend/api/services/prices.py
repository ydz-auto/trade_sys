"""
Prices Service - Price Comparison Logic
"""
from datetime import datetime
from ..schemas import PriceComparisonResponse, PriceSourceStatusResponse


def get_price_comparison(symbol: str) -> PriceComparisonResponse:
    """Get price comparison data"""
    prices = [
        {"exchange": "Binance", "price": 62345.78, "bid": 62344.23, "ask": 62347.33, "volume": 28.5},
        {"exchange": "OKX", "price": 62348.12, "bid": 62346.5, "ask": 62349.74, "volume": 15.2},
        {"exchange": "Bybit", "price": 62343.9, "bid": 62342.5, "ask": 62345.3, "volume": 12.8}
    ]
    return PriceComparisonResponse(
        symbol=symbol,
        prices=prices,
        priceSpread=4.22,
        bestBid="Bybit",
        bestAsk="OKX",
        timestamp=datetime.now().isoformat()
    )


def get_price_source_status() -> PriceSourceStatusResponse:
    """Get price source status"""
    return PriceSourceStatusResponse(
        sources={
            "Binance": {"status": "online", "lastUpdate": datetime.now().isoformat(), "latency": 45},
            "OKX": {"status": "online", "lastUpdate": datetime.now().isoformat(), "latency": 38},
            "Bybit": {"status": "online", "lastUpdate": datetime.now().isoformat(), "latency": 52}
        }
    )
