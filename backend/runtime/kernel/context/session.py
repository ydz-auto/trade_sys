"""
Runtime Session - Runtime 会话管理

核心职责:
1. 每种模式独立的 session
2. Session 状态隔离
3. Session 生命周期
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import uuid

from domain.trading_mode import TradingMode
from infrastructure.logging import get_logger
from infrastructure.utilities.runtime_clock import now_ms

logger = get_logger("runtime.session")


class SessionState(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"
    FAILED = "failed"


@dataclass
class SessionMetrics:
    events_processed: int = 0
    signals_generated: int = 0
    orders_executed: int = 0
    pnl: float = 0.0
    errors: int = 0


@dataclass
class RuntimeSession:
    session_id: str
    mode: TradingMode
    namespace: str
    state: SessionState = SessionState.CREATED
    created_at: datetime = field(default_factory=lambda: datetime.fromtimestamp(now_ms() / 1000))
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    
    state_data: Dict[str, Any] = field(default_factory=dict)
    positions: Dict[str, Any] = field(default_factory=dict)
    orders: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    
    metrics: SessionMetrics = field(default_factory=SessionMetrics)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float:
        if self.started_at:
            end = self.ended_at or datetime.fromtimestamp(now_ms() / 1000)
            return (end - self.started_at).total_seconds()
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "mode": self.mode.value,
            "namespace": self.namespace,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_seconds": self.duration_seconds,
            "metrics": {
                "events_processed": self.metrics.events_processed,
                "signals_generated": self.metrics.signals_generated,
                "orders_executed": self.metrics.orders_executed,
                "pnl": self.metrics.pnl,
                "errors": self.metrics.errors,
            },
        }


class SessionManager:
    _instance: Optional['SessionManager'] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._initialized = True
        
        self._sessions: Dict[str, RuntimeSession] = {}
        self._by_mode: Dict[TradingMode, List[str]] = {
            TradingMode.BACKTEST: [],
            TradingMode.PAPER: [],
            TradingMode.LIVE: [],
        }
        self._active_session: Optional[RuntimeSession] = None
        
        self._max_events_per_session = 10000
        
        self._stats = {
            "total_sessions": 0,
            "total_events": 0,
        }
        
        logger.info("SessionManager initialized")

    def create_session(
        self,
        mode: TradingMode,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> RuntimeSession:
        session_id = session_id or f"{mode.value}_{uuid.uuid4().hex[:8]}"
        namespace = f"session.{mode.value}.{session_id}"
        
        session = RuntimeSession(
            session_id=session_id,
            mode=mode,
            namespace=namespace,
            metadata=metadata or {},
        )
        
        self._sessions[session_id] = session
        self._by_mode[mode].append(session_id)
        self._stats["total_sessions"] += 1
        
        logger.info(f"Created session: {session_id} (mode={mode.value})")
        
        return session

    def start_session(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if not session:
            return False
        
        session.state = SessionState.ACTIVE
        session.started_at = datetime.fromtimestamp(now_ms() / 1000)
        self._active_session = session
        
        logger.info(f"Started session: {session_id}")
        return True

    def end_session(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if not session:
            return False
        
        session.state = SessionState.ENDED
        session.ended_at = datetime.fromtimestamp(now_ms() / 1000)
        
        if self._active_session and self._active_session.session_id == session_id:
            self._active_session = None
        
        logger.info(f"Ended session: {session_id} (duration={session.duration_seconds:.1f}s)")
        return True

    def pause_session(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if not session:
            return False
        
        session.state = SessionState.PAUSED
        logger.info(f"Paused session: {session_id}")
        return True

    def resume_session(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if not session:
            return False
        
        session.state = SessionState.ACTIVE
        logger.info(f"Resumed session: {session_id}")
        return True

    def get_session(self, session_id: str) -> Optional[RuntimeSession]:
        return self._sessions.get(session_id)

    def get_active_session(self) -> Optional[RuntimeSession]:
        return self._active_session

    def get_sessions_by_mode(self, mode: TradingMode) -> List[RuntimeSession]:
        return [
            self._sessions[sid]
            for sid in self._by_mode[mode]
            if sid in self._sessions
        ]

    def record_event(
        self,
        session_id: str,
        event_type: str,
        data: Dict[str, Any],
    ) -> None:
        session = self._sessions.get(session_id)
        if not session:
            return
        
        event = {
            "timestamp": datetime.fromtimestamp(now_ms() / 1000).isoformat(),
            "type": event_type,
            "data": data,
        }
        
        session.events.append(event)
        session.metrics.events_processed += 1
        self._stats["total_events"] += 1
        
        if len(session.events) > self._max_events_per_session:
            session.events = session.events[-self._max_events_per_session:]

    def record_signal(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session:
            session.metrics.signals_generated += 1

    def record_order(self, session_id: str, pnl: float = 0.0) -> None:
        session = self._sessions.get(session_id)
        if session:
            session.metrics.orders_executed += 1
            session.metrics.pnl += pnl

    def record_error(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session:
            session.metrics.errors += 1

    def set_state(self, session_id: str, key: str, value: Any) -> None:
        session = self._sessions.get(session_id)
        if session:
            session.state_data[key] = value

    def get_state(self, session_id: str, key: str) -> Any:
        session = self._sessions.get(session_id)
        if session:
            return session.state_data.get(key)
        return None

    def update_position(
        self,
        session_id: str,
        symbol: str,
        position: Dict[str, Any],
    ) -> None:
        session = self._sessions.get(session_id)
        if session:
            session.positions[symbol] = position

    def get_positions(self, session_id: str) -> Dict[str, Any]:
        session = self._sessions.get(session_id)
        if session:
            return session.positions.copy()
        return {}

    def clear_session(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session:
            session.state_data.clear()
            session.positions.clear()
            session.orders.clear()
            session.events.clear()
            logger.info(f"Cleared session data: {session_id}")

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_sessions": len(self._sessions),
            "active_session": self._active_session.session_id if self._active_session else None,
            "by_mode": {
                mode.value: len(sessions)
                for mode, sessions in self._by_mode.items()
            },
            "stats": self._stats.copy(),
        }


def get_session_manager() -> SessionManager:
    return SessionManager()
