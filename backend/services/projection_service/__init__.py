"""
Projection Service - Runtime State Projection Layer

将 Runtime 运行态投影到 UI 可读取的状态

架构：
    Services → Kafka → Projection Service → Redis/ClickHouse → API/WS → Frontend

职责：
1. 消费 Kafka 事件
2. 更新 Redis 状态（当前状态）
3. 写入 ClickHouse（历史记录）
4. 推送 WebSocket（实时通知）
"""

from .projections import (
    DashboardProjection,
    DecisionProjection,
    RiskProjection,
    PositionProjection,
    EventTimelineProjection,
)
from .state_keys import ProjectionKeys

__all__ = [
    "DashboardProjection",
    "DecisionProjection",
    "RiskProjection",
    "PositionProjection",
    "EventTimelineProjection",
    "ProjectionKeys",
]
