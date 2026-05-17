"""
Execution State Machine - 订单状态机模块

核心组件:
- OrderStateMachine: 订单状态机
- OrderJournal: 订单事件溯源
- IdempotencyManager: 幂等性管理
- RetryEngine: 重试引擎
- OrderReconciliation: 交易所状态同步
- ExecutionEngineWithStateMachine: 集成执行引擎
"""

from services.execution_service.state_machine.order_state_machine import (
    OrderEvent,
    OrderStateTransition,
    OrderJournalEntry,
    OrderJournal,
    IdempotencyManager,
    RetryConfig,
    RetryEngine,
    OrderStateMachine,
    VALID_TRANSITIONS,
    TERMINAL_STATES,
)
from services.execution_service.state_machine.reconciliation import (
    ReconciliationResult,
    SlippageRecord,
    ReconciliationConfig,
    SlippageTracker,
    OrderReconciliation,
)
from services.execution_service.state_machine.execution_engine import (
    ExecutionEngineWithStateMachine,
    get_execution_engine,
)

__all__ = [
    "OrderEvent",
    "OrderStateTransition",
    "OrderJournalEntry",
    "OrderJournal",
    "IdempotencyManager",
    "RetryConfig",
    "RetryEngine",
    "OrderStateMachine",
    "VALID_TRANSITIONS",
    "TERMINAL_STATES",
    "ReconciliationResult",
    "SlippageRecord",
    "ReconciliationConfig",
    "SlippageTracker",
    "OrderReconciliation",
    "ExecutionEngineWithStateMachine",
    "get_execution_engine",
]
