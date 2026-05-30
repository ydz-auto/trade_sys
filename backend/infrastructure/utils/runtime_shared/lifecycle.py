"""
Runtime Lifecycle - 统一的生命周期管理

所有 Runtime 共享的生命周期管理组件。
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from infrastructure.utilities.runtime_clock import now_ms


class RuntimePhase(Enum):
    """Runtime 阶段"""
    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class LifecycleState:
    """生命周期状态"""
    phase: RuntimePhase = RuntimePhase.CREATED
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    error_count: int = 0
    last_error: Optional[str] = None
    last_error_at: Optional[datetime] = None


class RuntimeLifecycle:
    """
    统一的 Runtime 生命周期管理
    
    职责：
    - 状态转换
    - 错误处理
    - 关闭回调
    """
    
    def __init__(self, name: str):
        self.name = name
        self.state = LifecycleState()
        
        self._error_handlers: List[Callable] = []
        self._shutdown_handlers: List[Callable] = []
        self._phase_handlers: Dict[RuntimePhase, List[Callable]] = {
            phase: [] for phase in RuntimePhase
        }
    
    def register_error_handler(self, handler: Callable) -> None:
        """注册错误处理器"""
        self._error_handlers.append(handler)
    
    def register_shutdown_handler(self, handler: Callable) -> None:
        """注册关闭处理器"""
        self._shutdown_handlers.append(handler)
    
    def on_phase(self, phase: RuntimePhase, handler: Callable) -> None:
        """注册阶段处理器"""
        self._phase_handlers[phase].append(handler)
    
    async def transition_to(self, phase: RuntimePhase) -> None:
        """转换到新阶段"""
        old_phase = self.state.phase
        self.state.phase = phase
        
        if phase == RuntimePhase.RUNNING:
            self.state.started_at = datetime.fromtimestamp(now_ms() / 1000)
        elif phase == RuntimePhase.STOPPED:
            self.state.stopped_at = datetime.fromtimestamp(now_ms() / 1000)
        
        for handler in self._phase_handlers[phase]:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(old_phase, phase)
                else:
                    handler(old_phase, phase)
            except Exception:
                pass

    async def transition_to_starting(self) -> None:
        """转换到启动阶段"""
        await self.transition_to(RuntimePhase.STARTING)

    async def transition_to_running(self) -> None:
        """转换到运行阶段"""
        await self.transition_to(RuntimePhase.RUNNING)

    async def transition_to_stopping(self) -> None:
        """转换到停止阶段"""
        await self.transition_to(RuntimePhase.STOPPING)

    async def transition_to_stopped(self) -> None:
        """转换到已停止阶段"""
        await self.transition_to(RuntimePhase.STOPPED)

    async def transition_to_error(self) -> None:
        """转换到错误阶段"""
        await self.transition_to(RuntimePhase.ERROR)
    
    async def handle_error(self, error: Exception) -> None:
        """处理错误"""
        self.state.error_count += 1
        self.state.last_error = str(error)
        self.state.last_error_at = datetime.fromtimestamp(now_ms() / 1000)
        
        for handler in self._error_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(error)
                else:
                    handler(error)
            except Exception:
                pass
    
    async def execute_shutdown_handlers(self) -> None:
        """执行关闭处理器"""
        for handler in self._shutdown_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler()
                else:
                    handler()
            except Exception:
                pass
    
    @property
    def uptime_seconds(self) -> float:
        """运行时长"""
        if self.state.started_at is None:
            return 0.0
        end = self.state.stopped_at or datetime.fromtimestamp(now_ms() / 1000)
        return (end - self.state.started_at).total_seconds()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "phase": self.state.phase.value,
            "started_at": self.state.started_at.isoformat() if self.state.started_at else None,
            "stopped_at": self.state.stopped_at.isoformat() if self.state.stopped_at else None,
            "uptime_seconds": self.uptime_seconds,
            "error_count": self.state.error_count,
            "last_error": self.state.last_error,
        }
