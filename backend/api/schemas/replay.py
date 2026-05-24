"""
Replay Schemas - 回放数据模型
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ReplayMode(str, Enum):
    """回放模式"""
    REALTIME = "realtime"
    FAST = "fast"
    STEP = "step"
    DETERMINISTIC = "deterministic"


class ReplayStatus(str, Enum):
    """回放状态"""
    PENDING = "pending"
    LOADING = "loading"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class CreateReplayRequest(BaseModel):
    """创建回放请求"""
    start_time: str = Field(..., description="开始时间 ISO格式")
    end_time: str = Field(..., description="结束时间 ISO格式")
    mode: ReplayMode = Field(default=ReplayMode.FAST, description="回放模式")
    symbols: List[str] = Field(default=["BTCUSDT"], description="交易对列表")
    exchanges: List[str] = Field(default=[], description="交易所列表")
    event_types: List[str] = Field(default=[], description="事件类型列表")
    speed: float = Field(default=1.0, description="回放速度倍数")


class ReplayResponse(BaseModel):
    """回放响应"""
    replay_id: str
    status: ReplayStatus
    total_events: int = 0
    processed_events: int = 0
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    current_time: Optional[str] = None
    error: Optional[str] = None
    stats: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None
    completed_at: Optional[str] = None
