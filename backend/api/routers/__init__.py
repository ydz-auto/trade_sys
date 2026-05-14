"""
Routers Package - FastAPI Endpoints
"""
from fastapi import APIRouter
from .health import router as health_router
from .dashboard import router as dashboard_router
from .prices import router as prices_router
from .factors import router as factors_router
from .alpha import router as alpha_router


api_router = APIRouter()
api_router.include_router(health_router, tags=["Health"])
api_router.include_router(dashboard_router, tags=["Dashboard"])
api_router.include_router(prices_router, tags=["Prices"])
api_router.include_router(factors_router, tags=["Factors"])
api_router.include_router(alpha_router, tags=["Alpha"])

__all__ = ["api_router"]
