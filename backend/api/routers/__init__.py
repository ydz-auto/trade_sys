"""
Routers Package - FastAPI Endpoints
"""
from fastapi import APIRouter
from .health import router as health_router
from .dashboard_v2 import router as dashboard_router
from .prices import router as prices_router
from .data import router as data_router
from .factors import router as factors_router
from .alpha import router as alpha_router
from .projection import router as projection_router
from .websocket import router as websocket_router
from .config import router as config_router
from .backtest import router as backtest_router
from .trading import router as trading_router
from .replay import router as replay_router
from .correlation import router as correlation_router
from .refresh import router as refresh_router
from .feature_matrix import router as feature_matrix_router
from .strategy import router as strategy_router
from .execution import router as execution_router
from .trading_mode import router as trading_mode_router


api_router = APIRouter()
api_router.include_router(health_router, tags=["Health"])
api_router.include_router(dashboard_router, tags=["Dashboard"])
api_router.include_router(trading_router, tags=["Trading"])
api_router.include_router(strategy_router, tags=["Strategy"])
api_router.include_router(execution_router, tags=["Execution"])
api_router.include_router(prices_router, tags=["Prices"])
api_router.include_router(data_router, tags=["Data"])
api_router.include_router(factors_router, tags=["Factors"])
api_router.include_router(feature_matrix_router, tags=["Feature Matrix"])
api_router.include_router(alpha_router, tags=["Alpha"])
api_router.include_router(projection_router, tags=["Projection"])
api_router.include_router(websocket_router, tags=["WebSocket"])
api_router.include_router(config_router, prefix="/config", tags=["Config"])
api_router.include_router(backtest_router, prefix="/backtest-api", tags=["Backtest"])
api_router.include_router(replay_router, tags=["Replay"])
api_router.include_router(correlation_router, prefix="/correlation", tags=["Correlation"])
api_router.include_router(refresh_router, tags=["Refresh"])
api_router.include_router(trading_mode_router, tags=["Trading Mode"])

__all__ = ["api_router"]
