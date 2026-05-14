"""
Alpha Router - Alpha Lifecycle Endpoints
"""
from fastapi import APIRouter, HTTPException
from typing import List
from ..schemas import (
    ProposalCreateRequest,
    ProposalUpdateRequest,
    ProposalResponse,
    SnapshotCreateRequest,
    SnapshotResponse,
    FactorLineageEntry,
)
from ..services import (
    get_all_proposals,
    create_proposal,
    update_proposal,
    get_all_snapshots,
    create_snapshot,
    get_factor_lineage,
)


router = APIRouter()


@router.get("/alpha/proposals", response_model=List[ProposalResponse])
async def get_proposals_endpoint():
    """Get all proposals"""
    return get_all_proposals()


@router.post("/alpha/proposals", response_model=ProposalResponse, status_code=201)
async def create_proposal_endpoint(request: ProposalCreateRequest):
    """Create new proposal"""
    return create_proposal(request)


@router.put("/alpha/proposals/{proposal_id}", response_model=ProposalResponse)
async def update_proposal_endpoint(proposal_id: str, request: ProposalUpdateRequest):
    """Update proposal"""
    result = update_proposal(proposal_id, request)
    if not result:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return result


@router.get("/alpha/snapshots", response_model=List[SnapshotResponse])
async def get_snapshots_endpoint():
    """Get all snapshots"""
    return get_all_snapshots()


@router.post("/alpha/snapshots", response_model=SnapshotResponse, status_code=201)
async def create_snapshot_endpoint(request: SnapshotCreateRequest):
    """Create new snapshot"""
    return create_snapshot(request)


@router.get("/alpha/factor-lineage", response_model=List[FactorLineageEntry])
async def get_factor_lineage_endpoint():
    """Get factor change history"""
    return get_factor_lineage()
