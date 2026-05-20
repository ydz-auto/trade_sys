"""
Runtime Lifecycle - Runtime 生命周期管理

核心职责:
1. 管理 runtime 生命周期状态
2. 状态转换验证
3. 生命周期事件通知
"""
from typing import Dict, Any, Optional, Callable, List
from enum import Enum
from datetime import datetime
from dataclasses import dataclass
import asyncio

from .registry import RuntimeState, RuntimeInfo, get_runtime_registry
from infrastructure.logging import get_logger

logger = get_logger("runtime.lifecycle")


class LifecycleEvent(str, Enum):
    PRE_START = "pre_start"
    POST_START = "post_start"
    PRE_STOP = "pre_stop"
    POST_STOP = "post_stop"
    PRE_PAUSE = "pre_pause"
    POST_PAUSE = "post_pause"
    PRE_RESUME = "pre_resume"
    POST_RESUME = "post_resume"
    ON_ERROR = "on_error"
    ON_RECOVER = "on_recover"


@dataclass
class LifecycleTransition:
    runtime_id: str
    from_state: RuntimeState
    to_state: RuntimeState
    timestamp: datetime
    success: bool
    error: Optional[str] = None


VALID_TRANSITIONS: Dict[RuntimeState, List[RuntimeState]] = {
    RuntimeState.REGISTERED: [RuntimeState.STARTING],
    RuntimeState.STARTING: [RuntimeState.RUNNING, RuntimeState.FAILED],
    RuntimeState.RUNNING: [RuntimeState.PAUSED, RuntimeState.DEGRADED, RuntimeState.STOPPING, RuntimeState.FAILED],
    RuntimeState.PAUSED: [RuntimeState.RUNNING, RuntimeState.STOPPING],
    RuntimeState.DEGRADED: [RuntimeState.RUNNING, RuntimeState.STOPPING, RuntimeState.FAILED],
    RuntimeState.STOPPING: [RuntimeState.STOPPED, RuntimeState.FAILED],
    RuntimeState.STOPPED: [RuntimeState.STARTING],
    RuntimeState.FAILED: [RuntimeState.RECOVERING, RuntimeState.STOPPING],
    RuntimeState.RECOVERING: [RuntimeState.RUNNING, RuntimeState.FAILED],
}


class RuntimeLifecycle:
    _instance: Optional['RuntimeLifecycle'] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._initialized = True
        self._registry = get_runtime_registry()
        
        self._event_handlers: Dict[LifecycleEvent, List[Callable]] = {
            event: [] for event in LifecycleEvent
        }
        
        self._transitions: List[LifecycleTransition] = []
        self._max_transitions = 1000
        
        self._stats = {
            "total_transitions": 0,
            "successful_transitions": 0,
            "failed_transitions": 0,
        }
        
        logger.info("RuntimeLifecycle initialized")

    def can_transition(self, runtime_id: str, target_state: RuntimeState) -> tuple[bool, str]:
        info = self._registry.get(runtime_id)
        if not info:
            return False, f"Runtime {runtime_id} not found"
        
        current_state = info.state
        valid_targets = VALID_TRANSITIONS.get(current_state, [])
        
        if target_state not in valid_targets:
            return False, f"Invalid transition: {current_state.value} -> {target_state.value}"
        
        return True, "OK"

    async def start(self, runtime_id: str) -> bool:
        can_start, reason = self.can_transition(runtime_id, RuntimeState.STARTING)
        if not can_start:
            logger.error(f"Cannot start {runtime_id}: {reason}")
            return False
        
        info = self._registry.get(runtime_id)
        
        await self._emit_event(LifecycleEvent.PRE_START, info)
        
        self._registry.update_state(runtime_id, RuntimeState.STARTING)
        
        try:
            if hasattr(info.instance, 'start'):
                await info.instance.start()
            
            self._registry.update_state(runtime_id, RuntimeState.RUNNING)
            self._record_transition(runtime_id, info.state, RuntimeState.RUNNING, True)
            
            await self._emit_event(LifecycleEvent.POST_START, info)
            
            logger.info(f"Runtime {runtime_id} started")
            return True
            
        except Exception as e:
            self._registry.update_state(runtime_id, RuntimeState.FAILED, str(e))
            self._record_transition(runtime_id, info.state, RuntimeState.FAILED, False, str(e))
            
            await self._emit_event(LifecycleEvent.ON_ERROR, info, error=str(e))
            
            logger.error(f"Failed to start {runtime_id}: {e}")
            return False

    async def stop(self, runtime_id: str) -> bool:
        info = self._registry.get(runtime_id)
        if not info:
            return False
        
        if info.state not in [RuntimeState.RUNNING, RuntimeState.PAUSED, RuntimeState.DEGRADED]:
            return False
        
        await self._emit_event(LifecycleEvent.PRE_STOP, info)
        
        self._registry.update_state(runtime_id, RuntimeState.STOPPING)
        
        try:
            if hasattr(info.instance, 'stop'):
                await info.instance.stop()
            
            self._registry.update_state(runtime_id, RuntimeState.STOPPED)
            self._record_transition(runtime_id, info.state, RuntimeState.STOPPED, True)
            
            await self._emit_event(LifecycleEvent.POST_STOP, info)
            
            logger.info(f"Runtime {runtime_id} stopped")
            return True
            
        except Exception as e:
            self._registry.update_state(runtime_id, RuntimeState.FAILED, str(e))
            self._record_transition(runtime_id, info.state, RuntimeState.FAILED, False, str(e))
            
            await self._emit_event(LifecycleEvent.ON_ERROR, info, error=str(e))
            
            logger.error(f"Failed to stop {runtime_id}: {e}")
            return False

    async def pause(self, runtime_id: str) -> bool:
        info = self._registry.get(runtime_id)
        if not info or info.state != RuntimeState.RUNNING:
            return False
        
        await self._emit_event(LifecycleEvent.PRE_PAUSE, info)
        
        try:
            if hasattr(info.instance, 'pause'):
                await info.instance.pause()
            
            self._registry.update_state(runtime_id, RuntimeState.PAUSED)
            self._record_transition(runtime_id, RuntimeState.RUNNING, RuntimeState.PAUSED, True)
            
            await self._emit_event(LifecycleEvent.POST_PAUSE, info)
            
            logger.info(f"Runtime {runtime_id} paused")
            return True
            
        except Exception as e:
            logger.error(f"Failed to pause {runtime_id}: {e}")
            return False

    async def resume(self, runtime_id: str) -> bool:
        info = self._registry.get(runtime_id)
        if not info or info.state != RuntimeState.PAUSED:
            return False
        
        await self._emit_event(LifecycleEvent.PRE_RESUME, info)
        
        try:
            if hasattr(info.instance, 'resume'):
                await info.instance.resume()
            
            self._registry.update_state(runtime_id, RuntimeState.RUNNING)
            self._record_transition(runtime_id, RuntimeState.PAUSED, RuntimeState.RUNNING, True)
            
            await self._emit_event(LifecycleEvent.POST_RESUME, info)
            
            logger.info(f"Runtime {runtime_id} resumed")
            return True
            
        except Exception as e:
            logger.error(f"Failed to resume {runtime_id}: {e}")
            return False

    async def recover(self, runtime_id: str) -> bool:
        info = self._registry.get(runtime_id)
        if not info or info.state != RuntimeState.FAILED:
            return False
        
        self._registry.update_state(runtime_id, RuntimeState.RECOVERING)
        
        try:
            if hasattr(info.instance, 'recover'):
                await info.instance.recover()
            else:
                await self.start(runtime_id)
            
            self._registry.update_state(runtime_id, RuntimeState.RUNNING)
            self._record_transition(runtime_id, RuntimeState.FAILED, RuntimeState.RUNNING, True)
            
            await self._emit_event(LifecycleEvent.ON_RECOVER, info)
            
            logger.info(f"Runtime {runtime_id} recovered")
            return True
            
        except Exception as e:
            self._registry.update_state(runtime_id, RuntimeState.FAILED, str(e))
            logger.error(f"Failed to recover {runtime_id}: {e}")
            return False

    def on_event(self, event: LifecycleEvent, handler: Callable) -> None:
        self._event_handlers[event].append(handler)

    async def _emit_event(self, event: LifecycleEvent, info: RuntimeInfo, error: Optional[str] = None) -> None:
        for handler in self._event_handlers[event]:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(info, error)
                else:
                    handler(info, error)
            except Exception as e:
                logger.error(f"Lifecycle event handler error: {e}")

    def _record_transition(
        self,
        runtime_id: str,
        from_state: RuntimeState,
        to_state: RuntimeState,
        success: bool,
        error: Optional[str] = None,
    ) -> None:
        transition = LifecycleTransition(
            runtime_id=runtime_id,
            from_state=from_state,
            to_state=to_state,
            timestamp=datetime.now(),
            success=success,
            error=error,
        )
        
        self._transitions.append(transition)
        self._stats["total_transitions"] += 1
        
        if success:
            self._stats["successful_transitions"] += 1
        else:
            self._stats["failed_transitions"] += 1
        
        if len(self._transitions) > self._max_transitions:
            self._transitions = self._transitions[-self._max_transitions:]

    def get_transitions(self, runtime_id: Optional[str] = None, limit: int = 100) -> List[LifecycleTransition]:
        transitions = self._transitions[-limit:]
        if runtime_id:
            transitions = [t for t in transitions if t.runtime_id == runtime_id]
        return transitions

    def get_stats(self) -> Dict[str, Any]:
        return {
            "stats": self._stats.copy(),
            "recent_transitions": [
                {
                    "runtime_id": t.runtime_id,
                    "from": t.from_state.value,
                    "to": t.to_state.value,
                    "timestamp": t.timestamp.isoformat(),
                    "success": t.success,
                }
                for t in self._transitions[-10:]
            ],
        }


def get_runtime_lifecycle() -> RuntimeLifecycle:
    return RuntimeLifecycle()
