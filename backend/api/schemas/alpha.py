"""
Alpha Schemas - Alpha Lifecycle Models
"""
from pydantic import BaseModel, Field
from typing import Dict, Optional, Any


class ProposalCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    type: str = "factor_adjustment"
    parameters: Dict[str, Any] = Field(default_factory=dict)
    created_by: str = "system"


class ProposalUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None


class ProposalResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    type: str
    status: str
    created_by: str
    created_at: str
    updated_at: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    backtest_results: Optional[Dict] = None


class SnapshotCreateRequest(BaseModel):
    name: Optional[str] = None
    type: str = "manual"
    description: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class SnapshotResponse(BaseModel):
    id: str
    timestamp: str
    name: Optional[str] = None
    type: str
    data: Dict[str, Any]
    description: Optional[str] = None


class FactorLineageEntry(BaseModel):
    id: str
    factor_type: str
    timestamp: str
    change_type: str
    old_value: Any
    new_value: Any
    reason: str
    user: Optional[str] = None
    related_proposal_id: Optional[str] = None
