from typing import List, Optional

from pydantic import Field

from infrastructure.messaging.schema.base import BaseMessage


class Signal(BaseMessage):
    signal: str = Field(description="信号名称，如 BTC_BULLISH")
    direction: str = Field(description="bullish / bearish / neutral")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="置信度")
    consensus: float = Field(default=0.0, ge=0.0, le=1.0, description="共识度")
    event_types: List[str] = Field(default_factory=list, description="触发的事件类型")
    assets: List[str] = Field(default_factory=list, description="相关品种")
    strength: float = Field(default=0.5, ge=0.0, le=1.0, description="信号强度")
    event_count: int = Field(default=0, description="聚合的事件数量")
    metadata: dict = Field(default_factory=dict, description="附加元数据")

    class Config:
        json_schema_extra = {
            "example": {
                "signal": "BTC_BULLISH",
                "direction": "bullish",
                "confidence": 0.75,
                "consensus": 0.8,
                "event_types": ["etf_inflow", "rate_cut"],
                "assets": ["BTC"],
                "strength": 0.7,
                "event_count": 3,
            }
        }

    @property
    def is_strong(self) -> bool:
        return self.confidence >= 0.7 and self.event_count >= 3

    @property
    def is_actionable(self) -> bool:
        return self.confidence >= 0.6 and self.event_count >= 2
