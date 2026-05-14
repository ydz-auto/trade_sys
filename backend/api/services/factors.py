"""
Factors Service - Factor Weight Logic
"""
import uuid
from datetime import datetime
from typing import List, Optional
from ..schemas import FactorItem, SuccessResponse
from .storage import get_factors, get_factor_lineage_data


def get_all_factors() -> List[FactorItem]:
    """Get all factors"""
    factors = get_factors()
    return [FactorItem(**f) for f in factors.values()]


def get_factor(factor_type: str) -> Optional[FactorItem]:
    """Get single factor"""
    factors = get_factors()
    f = factors.get(factor_type)
    return FactorItem(**f) if f else None


def update_factor_weight(factor_type: str, new_weight: float) -> SuccessResponse:
    """Update factor weight"""
    factors = get_factors()
    if factor_type not in factors:
        return SuccessResponse(success=False, message="Factor not found")
    
    old_weight = factors[factor_type]["weight"]
    
    factors[factor_type]["weight"] = new_weight
    
    lineage = get_factor_lineage_data()
    lineage.append({
        "id": f"lineage_{uuid.uuid4().hex[:12]}",
        "factor_type": factor_type,
        "timestamp": datetime.now().isoformat(),
        "change_type": "weight_update",
        "old_value": old_weight,
        "new_value": new_weight,
        "reason": "Manual weight update",
        "user": "api"
    })
    
    return SuccessResponse(success=True, message=f"{factor_type} weight updated successfully")
