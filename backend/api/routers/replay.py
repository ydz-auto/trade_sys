"""
Replay Router - 回放 API 端点
"""

from datetime import datetime
from typing import List

from fastapi import APIRouter, HTTPException

from api.schemas.replay import CreateReplayRequest, ReplayResponse, ReplayStatus
from api.services.replay_service import get_replay_service

router = APIRouter(prefix="/replay", tags=["Replay"])


@router.post("", response_model=ReplayResponse)
async def create_replay(request: CreateReplayRequest):
    """创建回放任务"""
    try:
        start_time = datetime.fromisoformat(request.start_time)
        end_time = datetime.fromisoformat(request.end_time)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid time format: {e}")
    
    if start_time >= end_time:
        raise HTTPException(status_code=400, detail="start_time must be before end_time")
    
    service = get_replay_service()
    session = await service.create_replay(
        start_time=start_time,
        end_time=end_time,
        mode=request.mode,
        symbols=request.symbols,
        exchanges=request.exchanges,
        event_types=request.event_types,
        speed=request.speed,
    )
    
    return session.to_response()


@router.get("/{replay_id}", response_model=ReplayResponse)
async def get_replay_status(replay_id: str):
    """获取回放状态"""
    service = get_replay_service()
    session = await service.get_status(replay_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Replay not found")
    
    return session.to_response()


@router.get("", response_model=List[ReplayResponse])
async def list_replays():
    """列出所有回放任务"""
    service = get_replay_service()
    sessions = await service.list_replays()
    return [s.to_response() for s in sessions]


@router.delete("/{replay_id}")
async def cancel_replay(replay_id: str):
    """取消回放任务"""
    service = get_replay_service()
    success = await service.cancel_replay(replay_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Replay not found or already completed")
    
    return {"message": "Replay cancelled", "replay_id": replay_id}


@router.delete("/{replay_id}/delete")
async def delete_replay(replay_id: str):
    """删除回放记录"""
    service = get_replay_service()
    success = await service.delete_replay(replay_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Replay not found")
    
    return {"message": "Replay deleted", "replay_id": replay_id}
