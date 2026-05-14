"""
Health Service - Health Check Endpoints
"""
from datetime import datetime
from ..schemas import HealthResponse


def get_health() -> HealthResponse:
    """Get health status"""
    return HealthResponse(
        status="healthy",
        mock_mode=True,
        timestamp=datetime.now()
    )
