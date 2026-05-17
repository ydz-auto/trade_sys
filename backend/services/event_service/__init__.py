"""
Event Service - 事件服务

业务逻辑：事件检测、事件分类
"""

from .handlers import EventDetector, get_event_detector

__all__ = [
    "EventDetector",
    "get_event_detector",
]
