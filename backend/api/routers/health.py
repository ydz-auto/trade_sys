"""
Health Router - Health Check Endpoints
"""
from fastapi import APIRouter
from ..schemas import HealthResponse
from ..services import get_health


router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return get_health()
