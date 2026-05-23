import logging
from typing import Dict, Any, Optional, Type

from infrastructure.messaging.schema.base_event import BaseEvent, SCHEMA_VERSION

logger = logging.getLogger("runtime.event_registry")


_event_classes: Dict[str, Type[BaseEvent]] = {}


def register_event(event_type: str, event_class: Type[BaseEvent]) -> None:
    """Register an event class for a given event type."""
    _event_classes[event_type] = event_class
    logger.debug(f"Registered event: {event_type} -> {event_class.__name__}")


def get_event_class(event_type: str) -> Type[BaseEvent]:
    """Get the registered event class for a type, fallback to BaseEvent."""
    return _event_classes.get(event_type, BaseEvent)


def parse_event(data: Dict[str, Any]) -> BaseEvent:
    """Parse dict into event using registry (simple, no versioning)."""
    event_type = data.get("event_type", "unknown")
    event_cls = get_event_class(event_type)
    return event_cls(**data)


def register_default_events() -> None:
    """Register default event types (for quick startup)."""
    from infrastructure.messaging.schema.base_event import (
        RawDataEvent,
        MarketEvent,
        FeatureEvent,
        SignalEvent,
        NarrativeEvent,
        DecisionEvent,
        RiskCheckedEvent,
        OrderEvent,
        FillEvent,
        SystemEvent,
        ErrorEvent,
        PipelineEventType,
    )

    register_event(PipelineEventType.RAW_DATA.value, RawDataEvent)
    register_event(PipelineEventType.MARKET.value, MarketEvent)
    register_event(PipelineEventType.FEATURE.value, FeatureEvent)
    register_event(PipelineEventType.SIGNAL.value, SignalEvent)
    register_event(PipelineEventType.NARRATIVE.value, NarrativeEvent)
    register_event(PipelineEventType.DECISION.value, DecisionEvent)
    register_event(PipelineEventType.RISK_CHECKED.value, RiskCheckedEvent)
    register_event(PipelineEventType.ORDER.value, OrderEvent)
    register_event(PipelineEventType.FILL.value, FillEvent)
    register_event(PipelineEventType.SYSTEM.value, SystemEvent)
    register_event(PipelineEventType.ERROR.value, ErrorEvent)
