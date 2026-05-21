"""
Infrastructure Event Module - 基础设施事件模块
"""

from infrastructure.event.event_time import (
    EventSource,
    EventTimeRecord,
    EventTimeConfig,
    EventTimeManager,
    get_event_time_manager,
    record_event_time,
)

from infrastructure.event.unified_event_processor import (
    EventContext,
    ProcessingResult,
    EventProcessor,
    UnifiedEventProcessor,
    CandleEventProcessor,
    TradeEventProcessor,
    get_unified_event_processor,
)

from infrastructure.event.cross_symbol_semantics import (
    SymbolAvailability,
    CrossSymbolAvailability,
    CrossSymbolEventSemantics,
    get_cross_symbol_semantics,
)

from infrastructure.event.event_ordering import (
    EventPriority,
    OrderedEvent,
    EventOrderingDeterminism,
    get_event_ordering,
    create_deterministic_event,
)

__all__ = [
    "EventSource",
    "EventTimeRecord",
    "EventTimeConfig",
    "EventTimeManager",
    "get_event_time_manager",
    "record_event_time",
    "EventContext",
    "ProcessingResult",
    "EventProcessor",
    "UnifiedEventProcessor",
    "CandleEventProcessor",
    "TradeEventProcessor",
    "get_unified_event_processor",
    "SymbolAvailability",
    "CrossSymbolAvailability",
    "CrossSymbolEventSemantics",
    "get_cross_symbol_semantics",
    "EventPriority",
    "OrderedEvent",
    "EventOrderingDeterminism",
    "get_event_ordering",
    "create_deterministic_event",
]
