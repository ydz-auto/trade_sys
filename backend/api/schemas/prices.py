"""
Prices Schemas - Price Comparison Models
"""
from pydantic import BaseModel
from typing import Dict, List, Any, Optional


class PriceComparisonResponse(BaseModel):
    symbol: str
    prices: List[Dict[str, Any]]
    priceSpread: float
    bestBid: Optional[str] = None
    bestAsk: Optional[str] = None
    timestamp: str


class PriceSourceStatusResponse(BaseModel):
    sources: Dict[str, Any]
