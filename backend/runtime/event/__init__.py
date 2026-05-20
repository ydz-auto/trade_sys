"""
Runtime Event Module

核心组件:
- EventNamespace: 事件命名空间
"""
from .namespace import (
    EventDomain,
    EventType,
    EventTopic,
    EventNamespace,
    get_event_namespace,
    ns_topic,
    ns_market,
    ns_signal,
    ns_execution,
    TOPICS,
)

__all__ = [
    "EventDomain",
    "EventType",
    "EventTopic",
    "EventNamespace",
    "get_event_namespace",
    "ns_topic",
    "ns_market",
    "ns_signal",
    "ns_execution",
    "TOPICS",
]
