"""
Prices Router - Price Comparison Endpoints
"""
from fastapi import APIRouter
from ..schemas import PriceComparisonResponse, PriceSourceStatusResponse
from ..services import get_price_comparison, get_price_source_status


router = APIRouter()


@router.get("/price-comparison/{symbol}", response_model=PriceComparisonResponse)
async def get_price_comparison_endpoint(symbol: str):
    """Get price comparison for symbol"""
    return get_price_comparison(symbol)


@router.get("/price-sources", response_model=PriceSourceStatusResponse)
async def get_price_sources_endpoint():
    """Get price source status"""
    return get_price_source_status()
