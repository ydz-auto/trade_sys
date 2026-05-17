"""
相关性分析类型定义
"""

from enum import Enum


class SignalDirection(Enum):
    """信号方向"""
    POSITIVE = "positive"      # 正相关
    NEGATIVE = "negative"      # 负相关
    NEUTRAL = "neutral"        # 无相关
    UNKNOWN = "unknown"        # 无法判断
