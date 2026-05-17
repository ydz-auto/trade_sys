"""
Dashboard Router - Trading Dashboard Endpoints
"""
from fastapi import APIRouter
from ..schemas import DashboardResponse
from ..services.dashboard import get_dashboard_data


router = APIRouter()


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard():
    """Get trading dashboard data from Projection"""
    return await get_dashboard_data()
