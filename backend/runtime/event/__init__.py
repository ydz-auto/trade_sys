"""
Runtime Event Module

核心组件:
- EventNamespace: 事件命名空间 (从 infrastructure 导入，注入 mode_provider)
"""
from infrastructure.messaging.event_namespace import (
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


def _init_runtime_event_namespace():
    from domain.trading_mode import get_trading_mode_manager
    get_event_namespace(mode_provider=lambda: get_trading_mode_manager().mode)


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
    "_init_runtime_event_namespace",
]
