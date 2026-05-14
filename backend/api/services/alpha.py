"""
Alpha Service - Alpha Lifecycle Logic
"""
import uuid
from datetime import datetime
from typing import List, Optional
from ..schemas import (
    ProposalCreateRequest,
    ProposalUpdateRequest,
    ProposalResponse,
    SnapshotCreateRequest,
    SnapshotResponse,
    FactorLineageEntry,
)
from .storage import get_proposals, get_snapshots, get_factor_lineage_data, get_factors


def get_all_proposals() -> List[ProposalResponse]:
    """Get all proposals"""
    proposals = get_proposals()
    return [
        ProposalResponse(
            id=p["id"],
            name=p["name"],
            description=p.get("description"),
            type=p["type"],
            status=p["status"],
            created_by=p["created_by"],
            created_at=p["created_at"],
            updated_at=p.get("updated_at", p["created_at"]),
            parameters=p.get("parameters", {}),
            backtest_results=p.get("backtest_results")
        ) for p in proposals
    ]


def create_proposal(request: ProposalCreateRequest) -> ProposalResponse:
    """Create proposal"""
    proposal_id = f"prop_{uuid.uuid4().hex[:12]}"
    now = datetime.now().isoformat()
    proposal = {
        "id": proposal_id,
        "name": request.name,
        "description": request.description,
        "type": request.type,
        "status": "draft",
        "created_by": request.created_by,
        "created_at": now,
        "updated_at": now,
        "parameters": request.parameters
    }
    proposals = get_proposals()
    proposals.append(proposal)
    return ProposalResponse(
        id=proposal["id"],
        name=proposal["name"],
        description=proposal.get("description"),
        type=proposal["type"],
        status=proposal["status"],
        created_by=proposal["created_by"],
        created_at=proposal["created_at"],
        updated_at=proposal["updated_at"],
        parameters=proposal["parameters"]
    )


def update_proposal(proposal_id: str, request: ProposalUpdateRequest) -> Optional[ProposalResponse]:
    """Update proposal"""
    proposals = get_proposals()
    for p in proposals:
        if p["id"] == proposal_id:
            if request.name:
                p["name"] = request.name
            if request.description:
                p["description"] = request.description
            if request.type:
                p["type"] = request.type
            if request.status:
                p["status"] = request.status
            if request.parameters:
                p["parameters"] = request.parameters
            p["updated_at"] = datetime.now().isoformat()
            return ProposalResponse(
                id=p["id"],
                name=p["name"],
                description=p.get("description"),
                type=p["type"],
                status=p["status"],
                created_by=p["created_by"],
                created_at=p["created_at"],
                updated_at=p["updated_at"],
                parameters=p["parameters"]
            )
    return None


def get_all_snapshots() -> List[SnapshotResponse]:
    """Get all snapshots"""
    snapshots = get_snapshots()
    return [
        SnapshotResponse(
            id=s["id"],
            timestamp=s["timestamp"],
            name=s.get("name"),
            type=s["type"],
            data=s["data"],
            description=s.get("description")
        ) for s in snapshots
    ]


def create_snapshot(request: SnapshotCreateRequest) -> SnapshotResponse:
    """Create snapshot"""
    snapshot_id = f"snap_{uuid.uuid4().hex[:12]}"
    factors = get_factors()
    snapshot = {
        "id": snapshot_id,
        "timestamp": datetime.now().isoformat(),
        "name": request.name,
        "type": request.type,
        "data": request.data or {"factors": factors.copy()},
        "description": request.description
    }
    snapshots = get_snapshots()
    snapshots.insert(0, snapshot)
    return SnapshotResponse(
        id=snapshot["id"],
        timestamp=snapshot["timestamp"],
        name=snapshot.get("name"),
        type=snapshot["type"],
        data=snapshot["data"],
        description=snapshot.get("description")
    )


def get_factor_lineage() -> List[FactorLineageEntry]:
    """Get factor lineage"""
    lineage = get_factor_lineage_data()
    return [
        FactorLineageEntry(
            id=e["id"],
            factor_type=e["factor_type"],
            timestamp=e["timestamp"],
            change_type=e["change_type"],
            old_value=e["old_value"],
            new_value=e["new_value"],
            reason=e["reason"],
            user=e.get("user"),
            related_proposal_id=e.get("related_proposal_id")
        ) for e in lineage
    ]
