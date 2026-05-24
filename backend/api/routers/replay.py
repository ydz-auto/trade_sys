from datetime import datetime
from typing import List

from fastapi import APIRouter, HTTPException

from api.schemas.replay import CreateReplayRequest, ReplayResponse, ReplayStatus
from application.commands.backtest import create_replay, cancel_replay, delete_replay
from application.queries.replay import get_replay_status, list_replays

router = APIRouter(prefix="/replay", tags=["Replay"])


@router.post("", response_model=ReplayResponse)
async def create_replay_endpoint(request: CreateReplayRequest):
    try:
        start_time = datetime.fromisoformat(request.start_time)
        end_time = datetime.fromisoformat(request.end_time)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid time format: {e}")

    if start_time >= end_time:
        raise HTTPException(status_code=400, detail="start_time must be before end_time")

    session = await create_replay(
        start_time=start_time,
        end_time=end_time,
        mode=request.mode,
        symbols=request.symbols,
        exchanges=request.exchanges,
        event_types=request.event_types,
        speed=request.speed,
    )

    return ReplayResponse(
        replay_id=session["replay_id"],
        status=ReplayStatus(session["status"]),
        total_events=session.get("total_events", 0),
        processed_events=session.get("processed_events", 0),
        start_time=session.get("start_time"),
        end_time=session.get("end_time"),
        current_time=session.get("current_time"),
        error=session.get("error"),
        stats=session.get("stats", {}),
        created_at=session.get("created_at"),
        completed_at=session.get("completed_at"),
    )


@router.get("/{replay_id}", response_model=ReplayResponse)
async def get_replay_status_endpoint(replay_id: str):
    session = await get_replay_status(replay_id)

    if not session:
        raise HTTPException(status_code=404, detail="Replay not found")

    return ReplayResponse(
        replay_id=session["replay_id"],
        status=ReplayStatus(session["status"]),
        total_events=session.get("total_events", 0),
        processed_events=session.get("processed_events", 0),
        start_time=session.get("start_time"),
        end_time=session.get("end_time"),
        current_time=session.get("current_time"),
        error=session.get("error"),
        stats=session.get("stats", {}),
        created_at=session.get("created_at"),
        completed_at=session.get("completed_at"),
    )


@router.get("", response_model=List[ReplayResponse])
async def list_replays_endpoint():
    sessions = await list_replays()
    return [
        ReplayResponse(
            replay_id=s["replay_id"],
            status=ReplayStatus(s["status"]),
            total_events=s.get("total_events", 0),
            processed_events=s.get("processed_events", 0),
            start_time=s.get("start_time"),
            end_time=s.get("end_time"),
            current_time=s.get("current_time"),
            error=s.get("error"),
            stats=s.get("stats", {}),
            created_at=s.get("created_at"),
            completed_at=s.get("completed_at"),
        )
        for s in sessions
    ]


@router.delete("/{replay_id}")
async def cancel_replay_endpoint(replay_id: str):
    success = await cancel_replay(replay_id)

    if not success:
        raise HTTPException(status_code=404, detail="Replay not found or already completed")

    return {"message": "Replay cancelled", "replay_id": replay_id}


@router.delete("/{replay_id}/delete")
async def delete_replay_endpoint(replay_id: str):
    success = await delete_replay(replay_id)

    if not success:
        raise HTTPException(status_code=404, detail="Replay not found")

    return {"message": "Replay deleted", "replay_id": replay_id}
