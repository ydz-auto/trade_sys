from typing import List, Optional

from pydantic import Field

from infrastructure.messaging.schema.base import BaseMessage
from domain.event.event_category import EventCategory  # NOTE: infrastructure → domain (type-only, allowed by architecture)
from domain.event.event_type import EventType  # NOTE: infrastructure → domain (type-only, allowed by architecture)
from domain.event.direction import Direction  # NOTE: infrastructure → domain (type-only, allowed by architecture)


class Event(BaseMessage):
    event_type: str = Field(description="事件类型")
    category: str = Field(description="事件分类 L1")
    asset: Optional[str] = Field(default=None, description="交易品种")
    direction: str = Field(description="bullish / bearish / neutral")
    strength: float = Field(default=0.5, ge=0.0, le=1.0, description="事件强度")
    sources: List[str] = Field(default_factory=list, description="数据来源")
    raw_data_ids: List[str] = Field(default_factory=list, description="原始数据ID列表")
    metadata: dict = Field(default_factory=dict, description="附加元数据")

    class Config:
        json_schema_extra = {
            "example": {
                "event_type": "etf_inflow",
                "category": "flow",
                "asset": "BTC",
                "direction": "bullish",
                "strength": 0.8,
                "sources": ["etf_tracker"],
            }
        }

    @classmethod
    def from_event_type(
        cls,
        event_type: EventType,
        asset: Optional[str] = None,
        strength: float = 0.5,
        sources: List[str] = None,
        **kwargs
    ) -> "Event":
        from domain.event.mapping import get_direction  # NOTE: infrastructure → domain (type-only, allowed by architecture)

        return cls(
            event_type=event_type.value,
            category=event_type.category.value,
            asset=asset,
            direction=get_direction(event_type).value,
            strength=strength,
            sources=sources or [],
            **kwargs
        )
