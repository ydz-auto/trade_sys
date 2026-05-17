"""
Replay Service - 回放服务

提供历史数据回放能力
"""

import asyncio
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from infrastructure.logging import get_logger
from infrastructure.replay.engine import ReplayEngine, ReplayConfig, ReplayMode as EngineReplayMode
from api.schemas.replay import ReplayMode, ReplayStatus, ReplayResponse

logger = get_logger("api.services.replay")


class ReplaySession:
    """回放会话"""
    def __init__(
        self,
        replay_id: str,
        start_time: datetime,
        end_time: datetime,
        mode: ReplayMode,
        symbols: List[str],
        exchanges: List[str],
        event_types: List[str],
        speed: float,
    ):
        self.replay_id = replay_id
        self.start_time = start_time
        self.end_time = end_time
        self.mode = mode
        self.symbols = symbols
        self.exchanges = exchanges
        self.event_types = event_types
        self.speed = speed
        
        self.status = ReplayStatus.PENDING
        self.total_events = 0
        self.processed_events = 0
        self.current_time: Optional[datetime] = None
        self.error: Optional[str] = None
        self.stats: Dict[str, Any] = {}
        self.created_at = datetime.utcnow()
        self.completed_at: Optional[datetime] = None
    
    def to_response(self) -> ReplayResponse:
        return ReplayResponse(
            replay_id=self.replay_id,
            status=self.status,
            total_events=self.total_events,
            processed_events=self.processed_events,
            start_time=self.start_time.isoformat(),
            end_time=self.end_time.isoformat(),
            current_time=self.current_time.isoformat() if self.current_time else None,
            error=self.error,
            stats=self.stats,
            created_at=self.created_at.isoformat(),
            completed_at=self.completed_at.isoformat() if self.completed_at else None,
        )


class ReplayService:
    """回放服务"""
    
    def __init__(self):
        self._sessions: Dict[str, ReplaySession] = {}
        self._running_tasks: Dict[str, asyncio.Task] = {}
    
    async def create_replay(
        self,
        start_time: datetime,
        end_time: datetime,
        mode: ReplayMode,
        symbols: List[str],
        exchanges: List[str],
        event_types: List[str],
        speed: float,
    ) -> ReplaySession:
        """创建回放任务"""
        replay_id = f"replay_{uuid.uuid4().hex[:12]}"
        
        session = ReplaySession(
            replay_id=replay_id,
            start_time=start_time,
            end_time=end_time,
            mode=mode,
            symbols=symbols,
            exchanges=exchanges,
            event_types=event_types,
            speed=speed,
        )
        
        self._sessions[replay_id] = session
        
        task = asyncio.create_task(self._run_replay(replay_id))
        self._running_tasks[replay_id] = task
        
        logger.info(f"Created replay task: {replay_id}")
        return session
    
    async def _run_replay(self, replay_id: str) -> None:
        """执行回放任务"""
        session = self._sessions.get(replay_id)
        if not session:
            return
        
        try:
            session.status = ReplayStatus.LOADING
            
            engine_config = ReplayConfig(
                mode=EngineReplayMode(session.mode.value),
                start_time=session.start_time,
                end_time=session.end_time,
                symbols=session.symbols,
                exchanges=session.exchanges,
                event_types=session.event_types,
                speed=session.speed,
            )
            
            engine = ReplayEngine(engine_config)
            await engine.initialize()
            
            await engine.create_session(
                start_time=session.start_time,
                end_time=session.end_time,
            )
            
            event_count = await engine.load_events()
            session.total_events = event_count
            session.status = ReplayStatus.RUNNING
            
            logger.info(f"Replay {replay_id} started with {event_count} events")
            
            await engine.run()
            
            session.status = ReplayStatus.COMPLETED
            session.processed_events = event_count
            session.completed_at = datetime.utcnow()
            
            logger.info(f"Replay {replay_id} completed")
            
        except Exception as e:
            session.status = ReplayStatus.FAILED
            session.error = str(e)
            logger.error(f"Replay {replay_id} failed: {e}")
    
    async def get_status(self, replay_id: str) -> Optional[ReplaySession]:
        """获取回放状态"""
        return self._sessions.get(replay_id)
    
    async def list_replays(self) -> List[ReplaySession]:
        """列出所有回放任务"""
        return list(self._sessions.values())
    
    async def cancel_replay(self, replay_id: str) -> bool:
        """取消回放任务"""
        task = self._running_tasks.get(replay_id)
        if task and not task.done():
            task.cancel()
            
            session = self._sessions.get(replay_id)
            if session:
                session.status = ReplayStatus.FAILED
                session.error = "Cancelled by user"
            
            logger.info(f"Replay {replay_id} cancelled")
            return True
        return False
    
    async def delete_replay(self, replay_id: str) -> bool:
        """删除回放记录"""
        if replay_id in self._sessions:
            await self.cancel_replay(replay_id)
            del self._sessions[replay_id]
            if replay_id in self._running_tasks:
                del self._running_tasks[replay_id]
            logger.info(f"Replay {replay_id} deleted")
            return True
        return False


_replay_service: Optional[ReplayService] = None


def get_replay_service() -> ReplayService:
    """获取回放服务单例"""
    global _replay_service
    if _replay_service is None:
        _replay_service = ReplayService()
    return _replay_service
