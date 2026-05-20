"""
Runtime Kernel - Runtime 核心模块

这是整个 Runtime Trading System 的核心，包含:
- ExecutionRouter: 统一下单入口
- RuntimeIsolation: namespace 隔离
- RuntimeStateStore: 统一状态存储
- EventNamespace: 事件命名空间

架构:
    TradeModeManager
           │
    ───────────────────────
    Market Runtime
           ↓
    Feature Runtime
           ↓
    Behaviour Runtime
           ↓
    Strategy Runtime
           ↓
    Execution Router  ← 本模块
       ├─ Paper Execution
       └─ Live Execution
           ↓
    Portfolio Runtime
           ↓
    Risk Runtime
           ↓
    Projection Runtime
           ↓
    RuntimeStateStore  ← 本模块
           ↓
    WebSocket Gateway
           ↓
    Frontend Runtime UI
"""
from .execution import (
    ExecutionRouter,
    ExecutionRoute,
    ExecutionBlockedError,
    get_execution_router,
    safe_execute,
)

from .isolation import (
    RuntimeNamespace,
    RuntimeIsolation,
    get_runtime_isolation,
    ns_topic,
    ns_event,
)

from .state import (
    StateSnapshot,
    RuntimeStateStore,
    get_runtime_state_store,
    set_state,
    get_state,
)

from .event import (
    EventDomain,
    EventType,
    EventNamespace,
    get_event_namespace,
)

__all__ = [
    "ExecutionRouter",
    "ExecutionRoute",
    "ExecutionBlockedError",
    "get_execution_router",
    "safe_execute",
    
    "RuntimeNamespace",
    "RuntimeIsolation",
    "get_runtime_isolation",
    "ns_topic",
    "ns_event",
    
    "StateSnapshot",
    "RuntimeStateStore",
    "get_runtime_state_store",
    "set_state",
    "get_state",
    
    "EventDomain",
    "EventType",
    "EventNamespace",
    "get_event_namespace",
]
