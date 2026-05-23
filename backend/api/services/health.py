"""
Health Service - Health Check Endpoints
"""
import os
from datetime import datetime
from ..schemas import HealthResponse


def get_health() -> HealthResponse:
    """Get health status"""
    mock_mode = os.getenv("DATA_MOCK_MODE", "false").lower() == "true" or \
                os.getenv("DASHBOARD_MOCK", "false").lower() == "true"
    
    return HealthResponse(
        status="healthy",
        mock_mode=mock_mode,
        timestamp=datetime.now()
    )
