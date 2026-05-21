"""
Analysis Types - 分析领域类型定义
"""
from enum import Enum


class SignalDirection(Enum):
    """信号方向"""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


__all__ = [
    "SignalDirection",
]
