"""
Projection Implementations

每个 Projection 负责：
1. 消费特定类型的 Kafka 事件
2. 更新 Redis 状态
3. 可选：写入 ClickHouse
4. 可选：推送 WebSocket
"""

from .base import BaseProjection
from .dashboard_projection import DashboardProjection
from .decision_projection import DecisionProjection
from .risk_projection import RiskProjection
from .position_projection import PositionProjection
from .event_timeline_projection import EventTimelineProjection

__all__ = [
    "BaseProjection",
    "DashboardProjection",
    "DecisionProjection",
    "RiskProjection",
    "PositionProjection",
    "EventTimelineProjection",
]
