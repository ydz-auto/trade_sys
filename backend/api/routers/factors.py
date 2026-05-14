"""
Factors Router - Factor Weight Endpoints
"""
from fastapi import APIRouter, HTTPException
from typing import List
from ..schemas import FactorItem, UpdateFactorWeightRequest, SuccessResponse
from ..services import get_all_factors, get_factor, update_factor_weight


router = APIRouter()


@router.get("/factors", response_model=List[FactorItem])
async def get_factors_endpoint():
    """Get all factors with weights"""
    return get_all_factors()


@router.get("/factors/{factor_type}", response_model=FactorItem)
async def get_factor_endpoint(factor_type: str):
    """Get single factor"""
    factor = get_factor(factor_type)
    if not factor:
        raise HTTPException(status_code=404, detail=f"Factor {factor_type} not found")
    return factor


@router.put("/factors/{factor_type}/weight", response_model=SuccessResponse)
async def update_factor_weight_endpoint(
    factor_type: str,
    request: UpdateFactorWeightRequest
):
    """Update factor weight"""
    return update_factor_weight(factor_type, request.weight)
