"""
EventBus - DEPRECATED

This file is deprecated. EventBus functionality has been merged into RuntimeBus.
Use `from runtime.bus import get_runtime_bus` instead.
"""
import warnings
from typing import Dict, List, Optional, Any, Callable

from infrastructure.logging import get_logger

logger = get_logger("event_bus.deprecated")

# 发出废弃警告
warnings.warn(
    "EventBus is deprecated and merged into RuntimeBus. "
    "Import from runtime.bus instead.",
    DeprecationWarning,
    stacklevel=2
)

# 兼容导入
try:
    from runtime.bus import RuntimeBus, Subscription
    from runtime.bus import get_runtime_bus, get_event_bus, publish_event_to_bus
    from shared.contracts import StandardEvent, EventFilter, EventType, Source
except ImportError as e:
    logger.error(f"Failed to import from runtime.bus: {e}")
    raise

logger.warning(
    "services.data_service.event_bus.event_bus is deprecated. "
    "Use runtime.bus instead."
)


# 导出兼容别名
__all__ = [
    "EventBus",
    "Subscription",
    "StrategyEventHandler",
    "get_event_bus",
    "publish_event",
]


def EventBus(*args, **kwargs):
    """兼容构造函数（返回 RuntimeBus）"""
    logger.warning(
        "EventBus class is deprecated, use get_runtime_bus() instead."
    )
    return get_runtime_bus()


def StrategyEventHandler(*args, **kwargs):
    """兼容构造函数（deprecated）"""
    logger.warning(
        "StrategyEventHandler is deprecated."
    )
    raise NotImplementedError(
        "StrategyEventHandler is deprecated, use RuntimeBus.subscribe() instead."
    )


def publish_event(event: StandardEvent):
    """兼容函数（deprecated）"""
    logger.warning(
        "publish_event() is deprecated, use runtime.bus.publish_event() instead."
    )
    return publish_event_to_bus(event)
