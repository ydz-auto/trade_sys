"""
Signal Runtime - 生命周期管理

职责：
- 启动/停止流程
- 错误恢复
- 状态转换
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from enum import Enum

from infrastructure.utilities.runtime_clock import now_ms


class RuntimePhase(Enum):
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class LifecycleState:
    """生命周期状态"""
    phase: RuntimePhase
    started_at: Optional[datetime]
    stopped_at: Optional[datetime]
    error_count: int
    last_error: Optional[str]


class SignalLifecycle:
    """
    Signal Runtime 生命周期管理
    
    只负责运行时生命周期，不包含业务逻辑。
    """
    
    def __init__(self, config):
        self.config = config
        self.state = LifecycleState(
            phase=RuntimePhase.STOPPED,
            started_at=None,
            stopped_at=None,
            error_count=0,
            last_error=None,
        )
        
        self._error_handlers: List[Callable] = []
        self._shutdown_handlers: List[Callable] = []
    
    def register_error_handler(self, handler: Callable) -> None:
        """注册错误处理器"""
        self._error_handlers.append(handler)
    
    def register_shutdown_handler(self, handler: Callable) -> None:
        """注册关闭处理器"""
        self._shutdown_handlers.append(handler)
    
    async def start(self) -> None:
        """启动"""
        self.state.phase = RuntimePhase.STARTING
        self.state.started_at = datetime.fromtimestamp(now_ms() / 1000)
        self.state.phase = RuntimePhase.RUNNING
    
    async def stop(self) -> None:
        """停止"""
        self.state.phase = RuntimePhase.STOPPING
        
        for handler in self._shutdown_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler()
                else:
                    handler()
            except Exception as e:
                pass
        
        self.state.stopped_at = datetime.fromtimestamp(now_ms() / 1000)
        self.state.phase = RuntimePhase.STOPPED
    
    async def handle_error(self, error: Exception) -> None:
        """处理错误"""
        self.state.error_count += 1
        self.state.last_error = str(error)
        
        for handler in self._error_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(error)
                else:
                    handler(error)
            except Exception:
                pass
    
    def get_state(self) -> Dict[str, Any]:
        """获取状态"""
        return {
            "phase": self.state.phase.value,
            "started_at": self.state.started_at.isoformat() if self.state.started_at else None,
            "stopped_at": self.state.stopped_at.isoformat() if self.state.stopped_at else None,
            "error_count": self.state.error_count,
            "last_error": self.state.last_error,
        }
