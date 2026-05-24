from fastapi import APIRouter
from ..schemas import HealthResponse
from application.queries.system import get_health


router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    return get_health()
