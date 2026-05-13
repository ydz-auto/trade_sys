"""
事件 Schema 模块

提供统一的事件模型，支持全链路追踪
"""

from infrastructure.messaging.schema.base import BaseMessage
from infrastructure.messaging.schema.raw_data import RawData
from infrastructure.messaging.schema.event import Event
from infrastructure.messaging.schema.signal import Signal
from infrastructure.messaging.schema.decision import Decision, RiskCheckedDecision

from infrastructure.messaging.schema.canonical import (
    EventType,
    EventSource,
    BaseEvent,
    RawDataEvent,
    MarketEvent,
    AnalysisEvent,
    SignalEvent,
    DecisionEvent,
    RiskCheckedEvent,
    OrderEvent,
    FillEvent,
    PNLEvent,
    ErrorEvent,
    parse_event,
    generate_trace_id,
    generate_event_id,
)

__all__ = [
    "BaseMessage",
    "RawData",
    "Event",
    "Signal",
    "Decision",
    "RiskCheckedDecision",
    
    "EventType",
    "EventSource",
    "BaseEvent",
    "RawDataEvent",
    "MarketEvent",
    "AnalysisEvent",
    "SignalEvent",
    "DecisionEvent",
    "RiskCheckedEvent",
    "OrderEvent",
    "FillEvent",
    "PNLEvent",
    "ErrorEvent",
    "parse_event",
    "generate_trace_id",
    "generate_event_id",
]
