"""
Runtime State Machine - Runtime 状态机

核心职责:
1. 定义所有有效状态转换
2. 状态转换验证
3. 状态转换执行
4. 状态历史记录
"""
from typing import Dict, Any, Optional, List, Callable, Set
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import asyncio

from runtime.kernel.runtime_context import RuntimeState

try:
    from infrastructure.logging import get_logger
    logger = get_logger("runtime.state_machine")
except ImportError:
    import logging
    logger = logging.getLogger("runtime.state_machine")


class TransitionResult(str, Enum):
    SUCCESS = "success"
    INVALID = "invalid"
    BLOCKED = "blocked"
    FAILED = "failed"


@dataclass
class StateTransition:
    from_state: RuntimeState
    to_state: RuntimeState
    timestamp: datetime = field(default_factory=datetime.now)
    reason: str = ""
    success: bool = True
    error: Optional[str] = None


@dataclass
class StateMachineConfig:
    allow_force_transition: bool = False
    max_history: int = 100
    transition_timeout: float = 30.0


VALID_TRANSITIONS: Dict[RuntimeState, Set[RuntimeState]] = {
    RuntimeState.CREATED: {
        RuntimeState.STARTING,
    },
    RuntimeState.STARTING: {
        RuntimeState.RUNNING,
        RuntimeState.FAILED,
        RuntimeState.STOPPED,
    },
    RuntimeState.RUNNING: {
        RuntimeState.PAUSED,
        RuntimeState.DEGRADED,
        RuntimeState.STOPPING,
        RuntimeState.FAILED,
    },
    RuntimeState.PAUSED: {
        RuntimeState.RUNNING,
        RuntimeState.STOPPING,
        RuntimeState.FAILED,
    },
    RuntimeState.DEGRADED: {
        RuntimeState.RUNNING,
        RuntimeState.STOPPING,
        RuntimeState.FAILED,
    },
    RuntimeState.STOPPING: {
        RuntimeState.STOPPED,
        RuntimeState.FAILED,
    },
    RuntimeState.STOPPED: {
        RuntimeState.STARTING,
    },
    RuntimeState.FAILED: {
        RuntimeState.RECOVERING,
        RuntimeState.STOPPING,
    },
    RuntimeState.RECOVERING: {
        RuntimeState.RUNNING,
        RuntimeState.FAILED,
    },
}


class RuntimeStateMachine:
    _instance: Optional['RuntimeStateMachine'] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config: Optional[StateMachineConfig] = None):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._initialized = True
        self._config = config or StateMachineConfig()
        
        self._states: Dict[str, RuntimeState] = {}
        self._history: Dict[str, List[StateTransition]] = {}
        
        self._transition_handlers: List[Callable] = []
        self._state_handlers: Dict[RuntimeState, List[Callable]] = {
            state: [] for state in RuntimeState
        }
        
        self._stats = {
            "total_transitions": 0,
            "successful_transitions": 0,
            "failed_transitions": 0,
            "invalid_transitions": 0,
        }
        
        logger.info("RuntimeStateMachine initialized")

    def register(self, runtime_id: str, initial_state: RuntimeState = RuntimeState.CREATED) -> None:
        self._states[runtime_id] = initial_state
        self._history[runtime_id] = []
        logger.info(f"Registered runtime state: {runtime_id} -> {initial_state.value}")

    def unregister(self, runtime_id: str) -> None:
        self._states.pop(runtime_id, None)
        self._history.pop(runtime_id, None)

    def get_state(self, runtime_id: str) -> Optional[RuntimeState]:
        return self._states.get(runtime_id)

    def can_transition(
        self,
        runtime_id: str,
        target_state: RuntimeState,
    ) -> tuple[bool, str]:
        current_state = self._states.get(runtime_id)
        if not current_state:
            return False, f"Runtime {runtime_id} not registered"
        
        valid_targets = VALID_TRANSITIONS.get(current_state, set())
        
        if target_state in valid_targets:
            return True, "OK"
        
        if self._config.allow_force_transition:
            return True, "Force transition allowed"
        
        return False, f"Invalid transition: {current_state.value} -> {target_state.value}"

    async def transition(
        self,
        runtime_id: str,
        target_state: RuntimeState,
        reason: str = "",
        force: bool = False,
    ) -> TransitionResult:
        current_state = self._states.get(runtime_id)
        if not current_state:
            return TransitionResult.INVALID
        
        can_trans, msg = self.can_transition(runtime_id, target_state)
        
        if not can_trans and not force:
            self._stats["invalid_transitions"] += 1
            logger.warning(f"Invalid transition blocked: {runtime_id} {current_state.value} -> {target_state.value}")
            return TransitionResult.INVALID
        
        transition = StateTransition(
            from_state=current_state,
            to_state=target_state,
            reason=reason,
        )
        
        try:
            self._states[runtime_id] = target_state
            transition.success = True
            
            self._stats["total_transitions"] += 1
            self._stats["successful_transitions"] += 1
            
            if runtime_id not in self._history:
                self._history[runtime_id] = []
            self._history[runtime_id].append(transition)
            
            if len(self._history[runtime_id]) > self._config.max_history:
                self._history[runtime_id] = self._history[runtime_id][-self._config.max_history:]
            
            logger.info(f"State transition: {runtime_id} {current_state.value} -> {target_state.value}")
            
            await self._notify_handlers(runtime_id, transition)
            
            return TransitionResult.SUCCESS
            
        except Exception as e:
            transition.success = False
            transition.error = str(e)
            
            self._stats["failed_transitions"] += 1
            logger.error(f"Transition failed: {runtime_id} - {e}")
            
            return TransitionResult.FAILED

    async def _notify_handlers(self, runtime_id: str, transition: StateTransition) -> None:
        for handler in self._transition_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(runtime_id, transition)
                else:
                    handler(runtime_id, transition)
            except Exception as e:
                logger.error(f"Transition handler error: {e}")
        
        state_handlers = self._state_handlers.get(transition.to_state, [])
        for handler in state_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(runtime_id, transition)
                else:
                    handler(runtime_id, transition)
            except Exception as e:
                logger.error(f"State handler error: {e}")

    def on_transition(self, handler: Callable) -> None:
        self._transition_handlers.append(handler)

    def on_state(self, state: RuntimeState, handler: Callable) -> None:
        self._state_handlers[state].append(handler)

    def get_history(self, runtime_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        history = self._history.get(runtime_id, [])
        return [
            {
                "from": t.from_state.value,
                "to": t.to_state.value,
                "timestamp": t.timestamp.isoformat(),
                "reason": t.reason,
                "success": t.success,
                "error": t.error,
            }
            for t in history[-limit:]
        ]

    def get_all_states(self) -> Dict[str, str]:
        return {rid: state.value for rid, state in self._states.items()}

    def get_stats(self) -> Dict[str, Any]:
        return {
            "registered_runtimes": len(self._states),
            "stats": self._stats.copy(),
        }


def get_state_machine() -> RuntimeStateMachine:
    return RuntimeStateMachine()
